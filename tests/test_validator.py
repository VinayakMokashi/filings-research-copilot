"""The validator: checking an answer's sentences, revising it, and trimming what fails."""

from __future__ import annotations

import json

from copilot.agents.graph import answer_record
from copilot.agents.validator import (
    ASSESSMENT,
    CHECK_ROLE,
    check_answer,
    failing,
    labelled,
    passes,
    revise,
    revise_messages,
    to_answer,
    trim,
    verdict_record,
)
from copilot.answer.calculator import Calculation
from copilot.answer.context import Source
from copilot.answer.generate import SYSTEM_PROMPT, Answer
from copilot.eval.faithfulness import Faithfulness, SentenceCheck
from copilot.llm import FakeLLM

RISKS = Source(1, "NETFLIX_2022_10K", 12, "Netflix 10-K, page 13", "Competition is intense.", 5)
MEMBERS = Source(2, "NETFLIX_2022_10K", 30, "Netflix 10-K, page 31", "Members grew 4%.", 5)
TEXT = "Netflix calls competition intense [1]. Its members grew 9% [2]."


def answer(text: str = TEXT) -> Answer:
    return Answer(
        question="What does Netflix say about competition and members?",
        answerable=True,
        text=text,
        missing="",
        sources=[RISKS, MEMBERS],
        cited=[1, 2],
        calculations=[Calculation("c1", "4 + 5", 0, 9.0)],
    )


def verdict(*supported: bool | None) -> Faithfulness:
    texts = ["Netflix calls competition intense [1].", "Its members grew 9% [2]."]
    return Faithfulness(
        [
            SentenceCheck(text, [n] if ok is not None else [], ok)
            for n, (text, ok) in enumerate(zip(texts, supported, strict=True), start=1)
        ]
    )


def test_the_check_runs_on_the_small_role_with_the_cited_pages() -> None:
    reply = {"sentences": [{"n": 1, "supported": True}, {"n": 2, "supported": False}]}
    checker = FakeLLM([json.dumps(reply)])

    result = check_answer(checker, answer())

    assert checker.calls[0].role == CHECK_ROLE == "small"
    prompt = checker.calls[0].messages[-1]["content"]
    assert "Competition is intense." in prompt
    assert "4 + 5" in prompt
    assert [check.supported for check in result.checks] == [True, False]
    assert [check.text for check in failing(result)] == ["Its members grew 9% [2]."]


def test_failing_counts_sentences_that_cite_nothing() -> None:
    assert [check.text for check in failing(verdict(True, None))] == ["Its members grew 9% [2]."]


def test_a_revision_shows_the_answer_and_names_the_failing_sentences() -> None:
    failed = failing(verdict(True, None))

    messages = revise_messages(SYSTEM_PROMPT, "Q?", answer(), failed)

    assert messages[0]["content"] == SYSTEM_PROMPT
    prompt = messages[1]["content"]
    assert prompt.startswith("Question: Q?\n\nSources:\n\n[1] Netflix 10-K, page 13")
    assert f"Your answer:\n{TEXT}" in prompt
    assert "1. Its members grew 9% [2]. (it cites no source)" in prompt


def test_revise_returns_the_writer_s_new_answer() -> None:
    fixed = "Netflix calls competition intense [1]. Its members grew 4% [2]."
    reply = {"answerable": True, "answer": fixed, "calculations": [], "missing": ""}
    writer = FakeLLM([json.dumps(reply)])

    revised = revise(writer, SYSTEM_PROMPT, "Q?", answer(), failing(verdict(True, False)))

    assert writer.calls[0].role == "strong"
    assert revised.text == fixed
    assert revised.cited == [1, 2]
    assert revised.sources == [RISKS, MEMBERS]


def test_trim_keeps_the_verified_sentences() -> None:
    trimmed, dropped = trim(answer(), verdict(True, False))

    assert trimmed.text == "Netflix calls competition intense [1]."
    assert trimmed.cited == [1]
    assert trimmed.answerable
    assert dropped == ["Its members grew 9% [2]."]


def test_trim_with_nothing_verified_declines() -> None:
    trimmed, dropped = trim(answer(), verdict(False, False))

    assert not trimmed.answerable
    assert trimmed.text == ""
    assert trimmed.missing.startswith("an answer its sources support; unverified: ")
    assert len(dropped) == 2


def test_an_answer_survives_the_trip_through_the_state() -> None:
    original = answer()

    rebuilt = to_answer(answer_record(original), original.question)

    assert rebuilt.text == original.text
    assert rebuilt.sources == original.sources
    assert rebuilt.cited == original.cited
    assert rebuilt.calculations == original.calculations


JUDGEMENT = f"{ASSESSMENT} competition weighs on Netflix's growth [1]."


def judged(*supported: bool | None) -> Faithfulness:
    """A verdict on a fact and a labelled assessment, in that order."""
    texts = ["Netflix calls competition intense [1].", JUDGEMENT]
    return Faithfulness(
        [SentenceCheck(text, [1], ok) for text, ok in zip(texts, supported, strict=True)]
    )


def test_a_labelled_assessment_doesn_t_fail_the_answer() -> None:
    result = judged(True, False)

    assert labelled(JUDGEMENT)
    assert not labelled("Netflix calls competition intense [1].")
    assert failing(result) == []
    assert passes(result)
    assert not result.faithful  # the strict reading, as the evaluation's judge has it
    assert verdict_record(result)["faithful"] is True
    assert verdict_record(result)["assessments"] == 1


def test_an_assessment_alone_answers_nothing() -> None:
    result = judged(False, False)

    assert [check.text for check in failing(result)] == ["Netflix calls competition intense [1]."]
    assert not passes(result)
    trimmed, dropped = trim(answer(), result)
    assert not trimmed.answerable
    assert dropped == ["Netflix calls competition intense [1]."]


def test_trim_keeps_a_labelled_assessment_beside_a_verified_fact() -> None:
    result = Faithfulness(
        [
            SentenceCheck("Netflix calls competition intense [1].", [1], True),
            SentenceCheck("Its members grew 9% [2].", [2], False),
            SentenceCheck(JUDGEMENT, [1], False),
        ]
    )

    trimmed, dropped = trim(answer(), result)

    assert trimmed.text == f"Netflix calls competition intense [1]. {JUDGEMENT}"
    assert dropped == ["Its members grew 9% [2]."]


def test_a_revision_may_keep_a_labelled_judgement_and_scales_percentages() -> None:
    prompt = revise_messages(SYSTEM_PROMPT, "Q?", answer(), failing(verdict(True, False)))[1]

    assert 'beginning "Assessment:"' in prompt["content"]
    assert "multiplies by 100" in prompt["content"]
