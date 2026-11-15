"""The paced client's retries: a reply the provider refused as invalid JSON is tried again in
batch work, and once only in interactive use."""

from __future__ import annotations

from typing import Any

import pytest

from copilot.llm import LLMError, LLMResponse, user
from copilot.llm.pacing import RETRY_PAUSE_S, PacedLLM


class _Unparseable:
    """Its first reply is refused as JSON that doesn't parse; the next one is fine."""

    calls = 0

    def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            raise LLMError("The small model call failed: json_validate_failed", invalid_reply=True)
        return LLMResponse(text="{}", role="small", model="fake/small", latency_s=0.0)

    async def acomplete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        raise NotImplementedError


def test_a_batch_tries_a_refused_json_reply_again(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Unparseable()
    waits: list[float] = []
    monkeypatch.setattr("copilot.llm.pacing.time.sleep", waits.append)

    response = PacedLLM(client, pause_s=0.0).complete([user("hi")], role="small")

    assert response.text == "{}"
    assert client.calls == 2
    assert waits == [RETRY_PAUSE_S]


def test_interactive_use_tries_a_refused_json_reply_once() -> None:
    client = _Unparseable()

    with pytest.raises(LLMError) as raised:
        PacedLLM(client, pause_s=0.0, attempts=1).complete([user("hi")], role="small")

    assert raised.value.invalid_reply
    assert client.calls == 1
