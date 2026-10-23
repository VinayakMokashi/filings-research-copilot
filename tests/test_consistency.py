"""Self-consistency: sampled answers, their main figure, and the vote."""

from __future__ import annotations

import json

import pytest

from copilot.answer.consistency import TEMPERATURE, key_figure, sample, vote
from copilot.answer.context import Source
from copilot.answer.generate import Answer
from copilot.llm import FakeLLM

PAGE = Source(1, "3M_2018_10K", 59, "3M 10-K, page 60", "Capital expenditures 1,577", 5)


def answer(text: str, *, answerable: bool = True) -> Answer:
    return Answer(
        question="What was 3M's capital expenditure in 2018?",
        answerable=answerable,
        text=text,
        missing="" if answerable else "the cash flow statement",
        sources=[PAGE],
        cited=[1] if answerable else [],
    )


CAPEX = answer("3M's capital expenditure was $1,577 million in fiscal 2018 [1].")
BILLIONS = answer("Capital spending came to $1.577 billion in 2018 [1].")
WRONG = answer("3M's capital expenditure was $1,373 million in fiscal 2018 [1].")
REFUSAL = answer("", answerable=False)


def test_the_key_figure_is_the_first_one_given() -> None:
    figure = key_figure(answer("It was $1,577 million, up from $1,373 million [1]."))

    assert figure is not None
    assert figure.value == 1577
    assert key_figure(REFUSAL) is None
    assert key_figure(answer("Capital spending rose [1].")) is None


def test_the_most_common_figure_wins_whatever_its_scale() -> None:
    kept, agreement = vote([WRONG, CAPEX, BILLIONS])

    assert kept == 1
    assert agreement == pytest.approx(2 / 3)


def test_a_split_vote_keeps_the_first_answer() -> None:
    assert vote([CAPEX, WRONG]) == (0, 0.5)


def test_refusals_vote_together() -> None:
    kept, agreement = vote([CAPEX, REFUSAL, REFUSAL])

    assert kept == 1
    assert agreement == pytest.approx(2 / 3)


def test_vote_needs_answers() -> None:
    with pytest.raises(ValueError, match="No answers"):
        vote([])


def test_a_sample_is_one_seeded_answer_call_at_a_temperature() -> None:
    reply = {"answerable": True, "answer": CAPEX.text, "calculations": [], "missing": ""}
    llm = FakeLLM([json.dumps(reply)])

    sampled = sample(llm, CAPEX.question, [PAGE], seed=2)

    assert sampled.text == CAPEX.text
    call = llm.calls[0]
    assert call.role == "strong"
    assert call.extra["seed"] == 2
    assert call.extra["response_format"] == {"type": "json_object"}
    assert TEMPERATURE == 0.7
