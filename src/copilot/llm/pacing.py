"""Pacing for batch jobs on free model tiers: space out calls, retry rate limits, add up usage.

Groq's free tier allows about 8,000 tokens a minute per model. A batch of a hundred calls
sent back to back runs into that limit within seconds, so `PacedLLM` waits a fixed pause
after every call that actually reached the model (cache hits cost nothing and don't
wait), retries a rate-limited call after a growing pause, and adds up the latency and
tokens of the calls it makes, so a run can report what it cost.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from typing import Any

from copilot.llm.base import LLMClient, LLMError, LLMResponse, Message, ModelRole

ATTEMPTS = 4
RETRY_PAUSE_S = 30.0


class PacedLLM:
    """Wraps a client for batch work; see the module docstring."""

    def __init__(self, client: LLMClient, pause_s: float = 3.0) -> None:
        self._client = client
        self._pause_s = pause_s
        self.calls = 0
        self.latency_s = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def reset(self) -> None:
        self.calls, self.latency_s, self.prompt_tokens, self.completion_tokens = 0, 0.0, 0, 0

    def _count(self, response: LLMResponse) -> None:
        self.calls += 1
        self.latency_s += response.latency_s
        self.prompt_tokens += response.prompt_tokens or 0
        self.completion_tokens += response.completion_tokens or 0

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = self._client.complete(
                    messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
                )
                break
            except LLMError as exc:
                if not exc.rate_limited or attempt == ATTEMPTS:
                    raise
                time.sleep(RETRY_PAUSE_S * attempt)
        self._count(response)
        if not response.cached:
            time.sleep(self._pause_s)
        return response

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = await self._client.acomplete(
                    messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
                )
                break
            except LLMError as exc:
                if not exc.rate_limited or attempt == ATTEMPTS:
                    raise
                await asyncio.sleep(RETRY_PAUSE_S * attempt)
        self._count(response)
        if not response.cached:
            await asyncio.sleep(self._pause_s)
        return response
