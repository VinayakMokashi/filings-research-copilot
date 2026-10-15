"""Types shared by every LLM client: messages, responses, errors and the client protocol."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict

ModelRole = Literal["strong", "fast"]
"""`strong` for hard reasoning (SQL, synthesis); `fast` for cheap, frequent calls."""


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


def system(content: str) -> Message:
    return {"role": "system", "content": content}


def user(content: str) -> Message:
    return {"role": "user", "content": content}


def assistant(content: str) -> Message:
    return {"role": "assistant", "content": content}


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """One completed model call, with what it cost and how it was served."""

    text: str
    role: ModelRole
    model: str
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    reasoning: str | None = None
    fallback_used: bool = False


class LLMError(RuntimeError):
    """A model call failed after retries and fallbacks.

    `rate_limited` is set when the role's own model was refused for quota reasons, which
    clears with time; callers can then ask the user to retry later instead of showing a raw
    error. Only that model's error decides the flag: when the fallbacks fail too, LiteLLM
    re-raises the role model's error, so a fallback that was rate-limited after a server
    error or timeout still leaves `rate_limited=False`.
    """

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


class LLMClient(Protocol):
    """What the rest of the system depends on: the real gateway and the fake both fit."""

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse: ...

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse: ...
