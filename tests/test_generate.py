"""Grounded generation: parsing replies, filling calculations, checking citations."""

from __future__ import annotations

import dataclasses
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
    ratio = [run("c1", "6539 / 34229", 4)]
    assert (
        fill("Margin {c1*100}% ({ c1 / 0 }).", ratio) == "Margin 19.1037% ([calculation failed])."
    )
    assert fill("Margin {c1*100:.1f}% or {c1:,.2f}.", ratio) == "Margin 19.1% or 0.19."


def test_fill_doesnt_repeat_a_figure_the_model_wrote_out() -> None:
    changes = [run("c1", "1699000000-1577000000", 0), run("c2", "1501000000-1699000000", 0)]
    text = (
        "Capex was $1.577 billion in 2018, increased by $122 million to $1.699 billion in "
        "2019 {c1}, and decreased by $198 million to $1.501 billion in 2020 ({c2}) [1]."
    )

    assert fill(text, changes) == (
        "Capex was $1.577 billion in 2018, increased by $122 million to $1.699 billion in "
        "2019, and decreased by $198 million to $1.501 billion in 2020 [1]."
    )
    # The calculator works in the source's units: a table in thousands gives 7,737,590.
    thousands = [run("c1", "12899672 - 5162082", 0)]
    assert fill("A decline of $7,737,590 thousand ({c1}) [1].", thousands) == (
        "A decline of $7,737,590 thousand [1]."
    )
    # A written number that is one of the expression's operands is the input, not a copy.
    doubled = [run("c1", "200000000 - 100000000", 0)]
    raw = [100_000_000.0, 200_000_000.0]
    assert fill("From $100 million to $200 million, up ${c1} [1].", doubled, raw) == (
        "From $100 million to $200 million, up $100 million [1]."
    )
    # A small result counts against an amount ("$204 million"), not a bare number ("5%").
    small = [run("c1", "1577 - 1373", 0)]
    assert (
        fill("An increase of $204 million {c1} [3].", small) == "An increase of $204 million [3]."
    )
    rise = [run("c1", "105 - 100", 0)]
    assert fill("A 5% rise to $105 million, up {c1} [1].", rise) == (
        "A 5% rise to $105 million, up 5 [1]."
    )
    # Only the placeholder's own sentence counts.
    assert fill("It rose by $122 million [1]. Then by {c1} [2].", changes[:1]) == (
        "It rose by $122 million [1]. Then by 122,000,000 [2]."
    )


def test_fill_writes_large_results_and_falls_readably() -> None:
    changes = [run("c1", "6434000000-1248000000", 0), run("c2", "7747000000-8920000000", 0)]
    database = [1_248_000_000.0, 6_434_000_000.0, 7_747_000_000.0, 8_920_000_000.0]

    assert fill("Income rose by {c1} and then fell by {c2} [1].", changes, database) == (
        "Income rose by 5.186 billion and then fell by 1.173 billion [1]."
    )
    assert fill("A change of {c2} [1].", changes, database) == "A change of -1.173 billion [1]."
    assert fill("A decline of ${c2} [1].", changes) == "A decline of $1,173,000,000 [1]."
    # From a filing's table, perhaps in thousands, a large result keeps the text's units.
    thousands = [run("c1", "12899672 - 5162082", 0)]
    assert fill("Revenue fell by ${c1} thousand [1].", thousands) == (
        "Revenue fell by $7,737,590 thousand [1]."
    )
    # A scale word after the placeholder means the model scaled the result itself.
    assert fill("Up {c1} million [1].", changes, database) == "Up 5,186,000,000 million [1]."


def test_build_answer_writes_database_results_compactly() -> None:
    database = Source(1, "facts-database", -1, "Facts database", "net_income\n6,434,000,000", 9)
    reply = {
        "answerable": True,
        "answer": "Net income rose by ${c1} to $6.434 billion [1].",
        "calculations": [{"id": "c1", "expression": "6434000000 - 1248000000", "decimals": 0}],
        "missing": "",
    }

    answer = build_answer("q", [database], _reply(json.dumps(reply)))

    # 1,248,000,000 isn't in this source, so the result keeps its digits.
    assert answer.text == "Net income rose by $5,186,000,000 to $6.434 billion [1]."
    database = dataclasses.replace(database, text="net_income\n1,248,000,000\n6,434,000,000")
    answer = build_answer("q", [database], _reply(json.dumps(reply)))
    assert answer.text == "Net income rose by $5.186 billion to $6.434 billion [1]."


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
