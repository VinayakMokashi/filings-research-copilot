"""Pacing for batch jobs on free model tiers: space out calls, retry rate limits, add up usage.

Groq's free tier allows about 8,000 tokens a minute per model. A batch of a hundred calls
sent back to back runs into that limit within seconds, so `PacedLLM` waits after every
call that actually reached the model (cache hits cost nothing and don't wait): a fixed
pause, or, when it knows the limit, the time the limit takes to earn back the tokens the
call used, whichever is longer. An answer call of 4,000 tokens under a limit of 8,000 a
minute waits 30 seconds; a short rewrite waits the fixed pause. It also retries a
rate-limited call after a growing pause, and adds up the latency and tokens of the calls
it makes, in all and by model, so a run can report what it cost. Interactive use asks for
one attempt: a quick fallback or apology beats minutes of waiting for a quota.
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

    def __init__(
        self,
        client: LLMClient,
        pause_s: float = 3.0,
        tokens_per_minute: int | None = None,
        attempts: int = ATTEMPTS,
    ) -> None:
        self._client = client
        self._pause_s = pause_s
        self._tokens_per_minute = tokens_per_minute
        self._attempts = max(1, attempts)
        self.calls = 0
        self.latency_s = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tokens_by_model: dict[str, tuple[int, int]] = {}  # model: (prompt, completion)

    def reset(self) -> None:
        self.calls, self.latency_s, self.prompt_tokens, self.completion_tokens = 0, 0.0, 0, 0
        self.tokens_by_model = {}

    def pause_after(self, response: LLMResponse) -> float:
        """Seconds to wait after a call; see the module docstring."""
        if response.cached:
            return 0.0
        tokens = (response.prompt_tokens or 0) + (response.completion_tokens or 0)
        limit = self._tokens_per_minute
        return max(self._pause_s, 60.0 * tokens / limit if limit else 0.0)

    def _count(self, response: LLMResponse) -> None:
        self.calls += 1
        self.latency_s += response.latency_s
        self.prompt_tokens += response.prompt_tokens or 0
        self.completion_tokens += response.completion_tokens or 0
        prompt, completion = self.tokens_by_model.get(response.model, (0, 0))
        self.tokens_by_model[response.model] = (
            prompt + (response.prompt_tokens or 0),
            completion + (response.completion_tokens or 0),
        )

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        for attempt in range(1, self._attempts + 1):
            try:
                response = self._client.complete(
                    messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
                )
                break
            except LLMError as exc:
                if not exc.rate_limited or attempt == self._attempts:
                    raise
                time.sleep(RETRY_PAUSE_S * attempt)
        self._count(response)
        if pause := self.pause_after(response):
            time.sleep(pause)
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
        for attempt in range(1, self._attempts + 1):
            try:
                response = await self._client.acomplete(
                    messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
                )
                break
            except LLMError as exc:
                if not exc.rate_limited or attempt == self._attempts:
                    raise
                await asyncio.sleep(RETRY_PAUSE_S * attempt)
        self._count(response)
        if pause := self.pause_after(response):
            await asyncio.sleep(pause)
        return response
