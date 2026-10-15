"""A deterministic stand-in for the LLM gateway, for tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from copilot.llm.base import LLMError, LLMResponse, Message, ModelRole
from copilot.llm.reasoning import split_reasoning

ReplyFn = Callable[[Sequence[Message], ModelRole], str]


@dataclass(frozen=True, slots=True)
class FakeCall:
    messages: list[Message]
    role: ModelRole
    extra: dict[str, Any]


class FakeLLM:
    """Replays scripted replies (a list, consumed in order, or a function) and records calls."""

    def __init__(self, replies: Sequence[str] | ReplyFn = ()) -> None:
        if isinstance(replies, str):
            raise TypeError("FakeLLM takes a list of replies or a function, not one string.")
        self._reply_fn: ReplyFn | None = replies if callable(replies) else None
        self._queue: list[str] = [] if callable(replies) else list(replies)
        self.calls: list[FakeCall] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        self.calls.append(FakeCall(messages=list(messages), role=role, extra=dict(extra)))
        if self._reply_fn is not None:
            raw = self._reply_fn(messages, role)
        elif self._queue:
            raw = self._queue.pop(0)
        else:
            raise LLMError("FakeLLM has no scripted replies left.")

        text, reasoning = split_reasoning(raw)
        return LLMResponse(
            text=text,
            role=role,
            model=f"fake/{role}",
            latency_s=0.0,
            prompt_tokens=sum(len(m["content"].split()) for m in messages),
            completion_tokens=len(raw.split()),
            cost_usd=0.0,
            reasoning=reasoning,
        )

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        return self.complete(
            messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
        )
