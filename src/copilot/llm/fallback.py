"""A paid fallback with a daily cap, for the public deployment (ADR-0033).

Groq's free tier refuses a call once a model's quota for the minute or the day is spent,
and an interactive run doesn't wait for a quota to come back. With this on, a refused call
goes to the same role on a paid provider instead, until the day's spend reaches a cap.
After that, or if the paid call fails too, the caller sees Groq's refusal, and the visitor
gets the usual apology.

Only quota refusals fall back: a bad request or an outage would spend money to fail again.
The day's spend is read before each paid call and added to after it, so calls already in
flight can pass the cap by a fraction of a cent each. If the spend can't be read, nothing
is spent: an unknown total isn't under the cap.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, Protocol

from copilot.llm.base import LLMClient, LLMError, LLMResponse, Message, ModelRole
from copilot.logs import get_logger

log = get_logger(__name__)

# Counted for a paid call whose price is unknown, so the cap still holds. A strong call
# costs about $0.003 at list prices.
UNKNOWN_COST_USD = 0.01


class SpendStore(Protocol):
    def spent(self, day: date) -> float:
        """Dollars spent on paid calls on `day`."""
        ...

    def add(self, day: date, usd: float) -> None:
        """Count `usd` more against `day`."""
        ...


class MemorySpend:
    """Spend kept in the process, for tests."""

    def __init__(self) -> None:
        self.by_day: dict[date, float] = {}
        self._lock = threading.Lock()

    def spent(self, day: date) -> float:
        with self._lock:
            return self.by_day.get(day, 0.0)

    def add(self, day: date, usd: float) -> None:
        with self._lock:
            self.by_day[day] = self.by_day.get(day, 0.0) + usd


def utc_today() -> date:
    """The day the cap counts, which ends at midnight UTC like the question quotas."""
    return datetime.now(UTC).date()


class CappedFallback:
    """Sends the calls `primary` refuses for quota reasons to `paid`; see the module docstring."""

    def __init__(
        self,
        primary: LLMClient,
        paid: LLMClient,
        spend: SpendStore,
        cap_usd: float,
        today: Callable[[], date] = utc_today,
    ) -> None:
        self._primary = primary
        self._paid = paid
        self._spend = spend
        self._cap_usd = cap_usd
        self._today = today

    def _may_spend(self, refusal: LLMError) -> bool:
        if not refusal.rate_limited:
            return False
        try:
            spent = self._spend.spent(self._today())
        except Exception as exc:  # any failure means an unknown total
            log.warning("llm.paid_fallback.unknown_spend", error=type(exc).__name__)
            return False
        if spent >= self._cap_usd:
            log.warning("llm.paid_fallback.cap_reached", spent_usd=round(spent, 4))
            return False
        return True

    def _record(self, response: LLMResponse) -> LLMResponse:
        cost = UNKNOWN_COST_USD if response.cost_usd is None else response.cost_usd
        try:
            self._spend.add(self._today(), cost)
        except Exception as exc:  # the answer is paid for already, so still return it
            log.warning("llm.paid_fallback.unrecorded", error=type(exc).__name__, cost_usd=cost)
        log.info("llm.paid_fallback", role=response.role, model=response.model, cost_usd=cost)
        return replace(response, fallback_used=True)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        call: dict[str, Any] = {
            "role": role,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **extra,
        }
        try:
            return self._primary.complete(messages, **call)
        except LLMError as refusal:
            if not self._may_spend(refusal):
                raise
            try:
                response = self._paid.complete(messages, **call)
            except LLMError as failure:
                raise refusal from failure
        return self._record(response)

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        call: dict[str, Any] = {
            "role": role,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **extra,
        }
        try:
            return await self._primary.acomplete(messages, **call)
        except LLMError as refusal:
            if not await asyncio.to_thread(self._may_spend, refusal):
                raise
            try:
                response = await self._paid.acomplete(messages, **call)
            except LLMError as failure:
                raise refusal from failure
        return await asyncio.to_thread(self._record, response)
