from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from copilot.llm import FakeLLM, LLMClient, LLMError, Message, ModelRole, system, user


def test_replays_scripted_replies_in_order() -> None:
    fake = FakeLLM(["first", "<think>x</think>second"])

    first = fake.complete([user("q1")])
    second = fake.complete([system("be brief"), user("q2")], role="strong")

    assert (first.text, second.text, second.reasoning) == ("first", "second", "x")
    assert [call.role for call in fake.calls] == ["fast", "strong"]
    assert fake.calls[1].messages[0] == system("be brief")


def test_reply_function_sees_messages_and_role() -> None:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        return f"{role}:{messages[-1]['content']}"

    fake = FakeLLM(reply)

    assert fake.complete([user("ping")], role="strong").text == "strong:ping"


def test_raises_when_replies_run_out() -> None:
    with pytest.raises(LLMError):
        FakeLLM([]).complete([user("q")])


def test_rejects_a_single_string() -> None:
    with pytest.raises(TypeError, match="not one string"):
        FakeLLM("ok")


def test_fake_fits_the_client_protocol() -> None:
    client: LLMClient = FakeLLM(["ok"])

    response = asyncio.run(client.acomplete([user("q")], extra_option=True))

    assert response.text == "ok"
    assert response.cost_usd == 0.0
