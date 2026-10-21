"""Faithfulness: splitting answers into cited sentences, and reading the judge's checks."""

from __future__ import annotations

import json

from copilot.eval.faithfulness import check, faithfulness_messages, sentences
from copilot.llm import FakeLLM

NNBSP = "\N{NARROW NO-BREAK SPACE}"
SOURCES = {
    1: ("3M, Form 10-K for fiscal 2022, PDF page 48", "Purchases of PP&E (1,749)"),
    5: ("3M, Form 10-K for fiscal 2022, PDF page 46", "Property, plant and equipment - net 9,178"),
}


def test_sentences_keep_citations_after_the_full_stop_and_skip_decimals() -> None:
    text = (
        f"Capex was $1.749{NNBSP}billion{NNBSP}[1]. It was 19.06% of PP&E of $9.178 billion. [5] "
        "U.S. GAAP applies. Margins fell [1, 5]"
    )

    found = sentences(text)

    assert [s.text for s in found] == [
        f"Capex was $1.749{NNBSP}billion{NNBSP}[1].",
        "It was 19.06% of PP&E of $9.178 billion. [5]",
        "U.S. GAAP applies.",
        "Margins fell [1, 5]",
    ]
    assert [s.cited for s in found] == [[1], [5], [], [1, 5]]
    assert sentences("A [1]. B [7].", valid=[1])[1].cited == []


def test_the_judge_sees_only_the_cited_sources_and_the_calculations() -> None:
    checked = sentences("It was 19.06% of PP&E [1][5].")

    prompt = faithfulness_messages(checked, SOURCES, [("c1", "1749/9178*100", 19.0564)])[1][
        "content"
    ]

    assert "[5] 3M, Form 10-K for fiscal 2022, PDF page 46\nProperty" in prompt
    assert "- 1749/9178*100 = 19.06" in prompt
    assert prompt.endswith("1. It was 19.06% of PP&E [1][5]. (cites 1, 5)")


def test_check_reads_verdicts_and_counts_supporting_citations() -> None:
    reply = {
        "sentences": [
            {"n": 1, "supported": True, "supporting": [1]},
            {"n": 2, "supported": False, "supporting": []},
        ]
    }
    fake = FakeLLM([json.dumps(reply)])

    result = check(fake, "Capex was $1,749 million [1]. It rose [1][5]. So 3M is fine.", SOURCES)

    assert [c.supported for c in result.checks] == [True, False, None]
    assert (result.cited_sentences, result.supported_sentences) == (2, 1)
    assert (result.citations, result.supporting_citations) == (3, 1)
    assert not result.faithful
    assert fake.calls[0].role == "fast"


def test_uncited_answers_need_no_call_and_bad_replies_count_against() -> None:
    fake = FakeLLM([])

    uncited = check(fake, "Capex was $1,749 million.", SOURCES)
    broken = check(FakeLLM(["no idea"]), "Capex was $1,749 million [1].", SOURCES)

    assert fake.calls == []
    assert [c.supported for c in uncited.checks] == [None]
    assert [c.supported for c in broken.checks] == [False]
    assert broken.error is not None
    assert check(
        FakeLLM([json.dumps({"sentences": [{"n": 1, "supported": True}]})]), "A [1].", SOURCES
    ).faithful
