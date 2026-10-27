"""Query rewriting: prompts, parsing, HyDE passages, and pacing of model calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from copilot.llm import FakeLLM, LLMError, Message, ModelRole
from copilot.llm.base import LLMResponse
from copilot.llm.pacing import PacedLLM
from copilot.retrieval import rewrite as rw

QUESTION = (
    "What was 3M's capital expenditure in fiscal 2018, in USD millions? Answer from the "
    "cash flow statement."
)


def test_parse_queries_drops_markers_quotes_blanks_and_repeats() -> None:
    text = (
        '1. 3M capital expenditures 2018\n- "3M purchases of PP&E 2018"\n\n'
        "Query 3: 3M capex\n3M capex"
    )

    assert rw.parse_queries(text, limit=3) == [
        "3M capital expenditures 2018",
        "3M purchases of PP&E 2018",
        "3M capex",
    ]
    assert rw.parse_queries("a\nb\nc\nd", limit=2) == ["a", "b"]


def test_prompts_carry_the_question_and_the_task() -> None:
    for kind in rw.REWRITES:
        system_message, user_message = rw.rewrite_messages(kind, QUESTION)
        assert system_message["role"] == "system"
        assert user_message["content"].startswith(f"Question: {QUESTION}")


def test_expand_puts_the_question_first_and_marks_hyde_as_a_passage() -> None:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        task = messages[-1]["content"]
        if "Write the passage" in task:
            return "Purchases of property, plant and equipment were\n$1,577 million in 2018."
        if "List the separate facts" in task:
            return "3M capital expenditure 2018"
        return "3M cash flow statement 2018\n3M purchases of PP&E 2018\n3M capex 2018\nextra"

    searches = rw.expand(FakeLLM(reply), QUESTION, rw.REWRITES)

    assert searches[0] == rw.Search(QUESTION)
    assert [s.source for s in searches] == [
        "question",
        "multi",
        "multi",
        "multi",
        "hyde",
        "decompose",
    ]
    hyde = searches[4]
    assert hyde.passage
    assert hyde.text == "Purchases of property, plant and equipment were $1,577 million in 2018."


def test_an_empty_hyde_reply_adds_no_search() -> None:
    assert rw.rewrite(FakeLLM(["   "]), "hyde", QUESTION) == []


class _Flaky:
    """Refuses the first call for quota reasons, then answers."""

    def __init__(self) -> None:
        self.attempts = 0

    def complete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        self.attempts += 1
        if self.attempts == 1:
            raise LLMError("rate limited", rate_limited=True)
        return LLMResponse("ok", "fast", "fake", 0.25, prompt_tokens=10, completion_tokens=5)

    async def acomplete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        return self.complete(messages)


def test_paced_llm_retries_rate_limits_and_adds_up_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    monkeypatch.setattr("copilot.llm.pacing.time.sleep", pauses.append)
    flaky = _Flaky()
    paced = PacedLLM(flaky, pause_s=3.0)

    response = paced.complete([])

    assert response.text == "ok"
    assert flaky.attempts == 2
    assert pauses == [30.0, 3.0]
    assert (paced.calls, paced.prompt_tokens, paced.completion_tokens) == (1, 10, 5)
    assert paced.tokens_by_model == {"fake": (10, 5)}
    assert paced.latency_s == pytest.approx(0.25)
    paced.reset()
    assert (paced.calls, paced.tokens_by_model) == (0, {})


def test_paced_llm_with_one_attempt_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    monkeypatch.setattr("copilot.llm.pacing.time.sleep", pauses.append)
    flaky = _Flaky()

    with pytest.raises(LLMError):
        PacedLLM(flaky, pause_s=0.0, attempts=1).complete([])

    assert flaky.attempts == 1
    assert pauses == []


def test_paced_llm_waits_long_enough_to_earn_back_the_tokens() -> None:
    paced = PacedLLM(FakeLLM([]), pause_s=3.0, tokens_per_minute=8000)
    answer = LLMResponse("ok", "strong", "fake", 1.0, prompt_tokens=3800, completion_tokens=200)
    rewrite = LLMResponse("ok", "fast", "fake", 0.2, prompt_tokens=300, completion_tokens=40)

    assert paced.pause_after(answer) == pytest.approx(30.0)
    assert paced.pause_after(rewrite) == 3.0
    assert paced.pause_after(LLMResponse("ok", "strong", "fake", 0.0, cached=True)) == 0.0
    assert PacedLLM(FakeLLM([]), pause_s=3.0).pause_after(answer) == 3.0


def test_paced_llm_gives_up_on_other_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("copilot.llm.pacing.time.sleep", lambda seconds: None)

    with pytest.raises(LLMError):
        PacedLLM(FakeLLM([])).complete([])


def test_aexpand_matches_expand() -> None:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        task = messages[-1]["content"]
        return "A passage." if "Write the passage" in task else "query one\nquery two"

    together = asyncio.run(rw.aexpand(FakeLLM(reply), QUESTION, rw.REWRITES))

    assert together == rw.expand(FakeLLM(reply), QUESTION, rw.REWRITES)


def test_another_hyde_prompt_shows_its_examples_before_the_question(tmp_path: Path) -> None:
    path = tmp_path / "hyde.json"
    path.write_text(
        json.dumps(
            {
                "version": "2",
                "instruction": "Write the filing's passage.",
                "examples": [["What was Acme's revenue in 2022?", "Net sales were $1.0 billion."]],
            }
        ),
        encoding="utf-8",
    )
    prompt = rw.load_hyde_prompt(path)

    messages = rw.rewrite_messages("hyde", "What was 3M's capex?", prompt)

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == "Write the filing's passage."
    assert messages[-1]["content"] == "Question: What was 3M's capex?"
    assert rw.rewrite_messages("multi", "q", prompt) == rw.rewrite_messages("multi", "q")


def test_expand_writes_hyde_with_the_prompt_it_is_given() -> None:
    prompt = rw.HydePrompt("2", "Write the filing's passage.")
    llm = FakeLLM(["Capital expenditures were $1.6 billion."])

    searches = rw.expand(llm, "What was 3M's capex?", ("hyde",), prompt)

    assert searches[1].passage
    assert llm.calls[0].messages[0]["content"] == "Write the filing's passage."
