"""The paid fallback and its daily cap (ADR-0033). Clients are scripted, so no network is used."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from litellm.exceptions import RateLimitError
from litellm.router import Router
from pydantic import SecretStr

from copilot.agents.build import model_client
from copilot.api.services import readiness
from copilot.config import Settings
from copilot.llm import LLMError, LLMGateway, user
from copilot.llm.base import LLMResponse, Message, ModelRole
from copilot.llm.fallback import UNKNOWN_COST_USD, CappedFallback, MemorySpend
from copilot.llm.gateway import build_router, paid_settings

DAY = date(2026, 11, 2)
REFUSED = LLMError("The fast model call failed: RateLimitError", rate_limited=True)


class Scripted:
    """Answers each call with the next outcome: a reply's cost in dollars, or an error."""

    def __init__(self, *outcomes: float | LLMError | None, model: str = "groq/m") -> None:
        self.outcomes = list(outcomes)
        self.model = model
        self.roles: list[ModelRole] = []

    def complete(
        self, messages: Sequence[Message], *, role: ModelRole = "fast", **_: Any
    ) -> LLMResponse:
        self.roles.append(role)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, LLMError):
            raise outcome
        return LLMResponse(text="ok", role=role, model=self.model, latency_s=0.1, cost_usd=outcome)

    async def acomplete(
        self, messages: Sequence[Message], *, role: ModelRole = "fast", **extra: Any
    ) -> LLMResponse:
        return self.complete(messages, role=role, **extra)


class BrokenSpend:
    def spent(self, day: date) -> float:
        raise ConnectionError("Firestore unreachable")

    def add(self, day: date, usd: float) -> None:
        raise ConnectionError("Firestore unreachable")


def capped(
    primary: Scripted, paid: Scripted, spend: Any = None, cap: float = 0.5
) -> CappedFallback:
    return CappedFallback(primary, paid, spend or MemorySpend(), cap, today=lambda: DAY)


def test_an_answered_call_never_touches_the_paid_model() -> None:
    primary, paid, spend = Scripted(0.0), Scripted(), MemorySpend()

    response = capped(primary, paid, spend).complete([user("hi")])

    assert (response.model, response.fallback_used) == ("groq/m", False)
    assert paid.roles == []
    assert spend.by_day == {}


def test_a_refused_call_goes_to_the_same_role_on_the_paid_model() -> None:
    primary, paid = Scripted(REFUSED), Scripted(0.003, model="cerebras/m")
    spend = MemorySpend()

    response = capped(primary, paid, spend).complete([user("hi")], role="strong")

    assert paid.roles == ["strong"]
    assert (response.model, response.fallback_used) == ("cerebras/m", True)
    assert spend.spent(DAY) == pytest.approx(0.003)


def test_only_quota_refusals_fall_back() -> None:
    broken = LLMError("The fast model call failed: BadRequestError")
    primary, paid = Scripted(broken), Scripted(0.003)

    with pytest.raises(LLMError) as info:
        capped(primary, paid).complete([user("hi")])

    assert info.value is broken
    assert paid.roles == []


def test_the_cap_stops_paid_calls_for_the_rest_of_the_day() -> None:
    spend = MemorySpend()
    spend.add(DAY, 0.5)
    primary, paid = Scripted(REFUSED), Scripted(0.003)

    with pytest.raises(LLMError) as info:
        capped(primary, paid, spend).complete([user("hi")])

    assert info.value.rate_limited
    assert paid.roles == []


def test_a_new_day_starts_under_the_cap() -> None:
    spend = MemorySpend()
    spend.add(date(2026, 11, 1), 0.5)
    primary, paid = Scripted(REFUSED), Scripted(0.003)

    assert capped(primary, paid, spend).complete([user("hi")]).fallback_used


def test_calls_add_up_to_the_cap() -> None:
    spend = MemorySpend()
    primary = Scripted(*[REFUSED] * 4)
    paid = Scripted(0.2, 0.2, 0.2)
    fallback = capped(primary, paid, spend)

    for _ in range(3):  # 0.0, 0.2 and 0.4 are under the cap; each call is allowed
        fallback.complete([user("hi")])
    with pytest.raises(LLMError):
        fallback.complete([user("hi")])  # 0.6 is not

    assert len(paid.roles) == 3
    assert spend.spent(DAY) == pytest.approx(0.6)


def test_an_unknown_spend_spends_nothing() -> None:
    primary, paid = Scripted(REFUSED), Scripted(0.003)

    with pytest.raises(LLMError) as info:
        capped(primary, paid, BrokenSpend()).complete([user("hi")])

    assert info.value is REFUSED
    assert paid.roles == []


def test_an_answer_is_kept_when_its_cost_cant_be_recorded() -> None:
    spend = MemorySpend()
    fallback = capped(Scripted(REFUSED), Scripted(0.003), spend)

    with patch.object(spend, "add", side_effect=ConnectionError("Firestore unreachable")):
        response = fallback.complete([user("hi")])

    assert response.fallback_used


def test_a_failed_paid_call_leaves_the_visitor_with_groqs_refusal() -> None:
    cerebras_down = LLMError("The fast model call failed: ServiceUnavailableError")
    primary, paid = Scripted(REFUSED), Scripted(cerebras_down)

    with pytest.raises(LLMError) as info:
        capped(primary, paid).complete([user("hi")])

    assert info.value is REFUSED
    assert info.value.__cause__ is cerebras_down


def test_an_unknown_price_still_counts_against_the_cap() -> None:
    spend = MemorySpend()

    capped(Scripted(REFUSED), Scripted(None), spend).complete([user("hi")])

    assert spend.spent(DAY) == UNKNOWN_COST_USD


def test_async_calls_fall_back_the_same_way() -> None:
    spend = MemorySpend()
    fallback = capped(Scripted(REFUSED, 0.0), Scripted(0.003, model="cerebras/m"), spend)

    paid_reply = asyncio.run(fallback.acomplete([user("hi")], role="small"))
    own_reply = asyncio.run(fallback.acomplete([user("hi")], role="small"))

    assert (paid_reply.model, paid_reply.fallback_used) == ("cerebras/m", True)
    assert (own_reply.model, own_reply.fallback_used) == ("groq/m", False)
    assert spend.spent(DAY) == pytest.approx(0.003)


# --- Where it is wired in ----------------------------------------------------------------


def test_paid_settings_put_every_role_on_its_paid_model() -> None:
    settings = paid_settings(Settings(_env_file=None))

    assert (settings.llm_strong_model, settings.llm_fast_model, settings.llm_small_model) == (
        "cerebras/gpt-oss-120b",
        "cerebras/qwen-3.8-27b",
        "cerebras/gpt-oss-120b",
    )


def test_only_the_api_with_a_spend_store_gets_the_fallback(tmp_path: Any) -> None:
    settings = Settings(
        _env_file=None, data_dir=tmp_path, llm_disk_cache=False, llm_paid_daily_usd=0.5
    )

    api = model_client(settings, "llm.jsonl", spend=MemorySpend())
    batch = model_client(settings, "llm.jsonl", batch=True, spend=MemorySpend())
    without = model_client(settings, "llm.jsonl")

    assert isinstance(api._client, CappedFallback)
    assert isinstance(batch._client, LLMGateway)
    assert isinstance(without._client, LLMGateway)


def test_the_fallback_sits_outside_the_disk_cache(tmp_path: Any) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, llm_paid_daily_usd=0.5)

    client = model_client(settings, "llm.jsonl", spend=MemorySpend())._client

    assert isinstance(client, CappedFallback)
    assert type(client._primary).__name__ == "CachedLLM"
    assert isinstance(client._paid, LLMGateway)


def test_with_the_fallback_on_a_rate_limit_is_not_retried() -> None:
    attempts = 0

    def refuse(*args: Any, **kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        raise RateLimitError(message="slow down", llm_provider="groq", model="m")

    for paid_daily_usd, expected in ((0.0, 3), (0.5, 1)):
        attempts = 0
        router = build_router(Settings(_env_file=None, llm_paid_daily_usd=paid_daily_usd))
        no_pause = patch.object(Router, "_time_to_sleep_before_retry", return_value=0)
        with no_pause, patch("litellm.completion", refuse), pytest.raises(RateLimitError):
            router.completion(model="fast", messages=[{"role": "user", "content": "hi"}])
        assert attempts == expected


def test_readiness_needs_the_paid_key_only_when_the_fallback_is_on(tmp_path: Any) -> None:
    off = Settings(_env_file=None, data_dir=tmp_path, qdrant_url="http://127.0.0.1:9")
    on = off.model_copy(update={"llm_paid_daily_usd": 0.5})
    keyed = on.model_copy(update={"cerebras_api_key": SecretStr("csk-test")})

    assert "paid_llm_key" not in readiness(off)
    assert readiness(on)["paid_llm_key"] is False
    assert readiness(keyed)["paid_llm_key"] is True
