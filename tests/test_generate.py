"""Grounded generation: parsing replies, filling calculations, checking citations."""

from __future__ import annotations

import json

import pytest

from copilot.answer.calculator import run
from copilot.answer.context import Source
from copilot.answer.generate import (
    answer_messages,
    build_answer,
    citations,
    fill,
    generate,
    normalise_citations,
    parse_draft,
)
from copilot.llm import FakeLLM
from copilot.llm.base import LLMResponse

SOURCES = [
    Source(1, "3M_2018_10K", 59, "3M, Form 10-K for fiscal 2018, PDF page 60", "Capex 1,577", 4),
    Source(2, "3M_2018_10K", 40, "3M, Form 10-K for fiscal 2018, PDF page 41", "Sales 32,765", 4),
]
GOOD = {
    "answerable": True,
    "answer": "Capex was $1,577 million [1], or {c1}% of sales [1][2].",
    "calculations": [{"id": "c1", "expression": "1,577 / 32,765 * 100", "decimals": 1}],
    "missing": "",
}


def _reply(text: str) -> LLMResponse:
    return LLMResponse(text, "strong", "fake/strong", 1.2, prompt_tokens=900, completion_tokens=80)


def test_parse_draft_tolerates_fences_and_prose() -> None:
    fenced = "Here you go:\n```json\n" + json.dumps(GOOD) + "\n```"

    assert parse_draft(json.dumps(GOOD)).answerable
    assert parse_draft(fenced).calculations[0].id == "c1"
    with pytest.raises(ValueError, match="no JSON object"):
        parse_draft("no json at all")
    with pytest.raises(ValueError, match="valid answer object"):
        parse_draft('{"answer": "missing the answerable flag"}')


def test_fill_and_citations() -> None:
    calculations = [run("c1", "1577 / 32765 * 100", 1)]

    assert (
        fill("It was {c1}% and { c2 }.", calculations) == "It was 4.8% and [calculation missing]."
    )
    assert citations("A [2]. B [1, 3][2]. C [10].") == [2, 1, 3, 10]


def test_build_answer_computes_cites_and_records_usage() -> None:
    answer = build_answer("q", SOURCES, _reply(json.dumps(GOOD)))

    assert answer.answerable
    assert answer.text == "Capex was $1,577 million [1], or 4.8% of sales [1][2]."
    assert answer.cited == [1, 2]
    assert [source.page for source in answer.cited_sources] == [59, 40]
    assert (answer.prompt_tokens, answer.completion_tokens, answer.latency_s) == (900, 80, 1.2)


def test_lenticular_citations_are_rewritten_as_square_brackets() -> None:
    left, right = "\N{LEFT BLACK LENTICULAR BRACKET}", "\N{RIGHT BLACK LENTICULAR BRACKET}"
    reply = dict(
        GOOD,
        answer=f"Capex was $1,577 million{left}1{right}, up{left}2\N{DAGGER}L4-L9{right}.",
        calculations=[],
    )

    answer = build_answer("q", SOURCES, _reply(json.dumps(reply)))

    assert normalise_citations(f"A{left} 1, 2 {right}.") == "A[1, 2]."
    assert answer.text == "Capex was $1,577 million[1], up[2]."
    assert answer.cited == [1, 2]


def test_bad_citations_and_unparseable_replies_are_recorded() -> None:
    wrong = dict(GOOD, answer="Capex was $1,577 million [1][7].", calculations=[])

    answer = build_answer("q", SOURCES, _reply(json.dumps(wrong)))
    broken = build_answer("q", SOURCES, _reply("Sorry, I can't help."))

    assert (answer.cited, answer.invalid_citations) == ([1], [7])
    assert not broken.answerable
    assert broken.error is not None


def test_generate_sends_numbered_sources_and_asks_for_json() -> None:
    fake = FakeLLM([json.dumps(GOOD)])

    generate(fake, "What was 3M's capex?", SOURCES)

    call = fake.calls[0]
    assert call.role == "strong"
    assert call.extra["response_format"] == {"type": "json_object"}
    prompt = call.messages[-1]["content"]
    assert "[1] 3M, Form 10-K for fiscal 2018, PDF page 60\nCapex 1,577" in prompt
    assert answer_messages("q", SOURCES)[0]["role"] == "system"
