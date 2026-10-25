"""The correctness judge: what it sees, what it skips, and how it reads replies."""

from __future__ import annotations

import json

import pytest

from copilot.eval.judge import (
    Figure,
    closest_figures,
    comparisons,
    distance,
    figures,
    judge,
    judge_messages,
    parse_verdict,
    strip_citations,
)
from copilot.llm import FakeLLM

QUESTION = "What was 3M's capital expenditure in fiscal 2018, in USD millions?"


def test_the_judge_sees_the_reference_and_the_answer_without_citations() -> None:
    messages = judge_messages(
        QUESTION, "$1577.00", "Capex was $1,577 million [3][4].", "Purchases of PP&E."
    )

    prompt = messages[-1]["content"]
    assert messages[0]["role"] == "system"
    assert "Reference answer: $1577.00" in prompt
    assert "How the reference was reached: Purchases of PP&E." in prompt
    assert "Candidate answer: Capex was $1,577 million." in prompt
    assert prompt.endswith("- reference 1577.00, closest candidate figure 1,577: 0.00% apart")
    assert "How the reference" not in judge_messages(QUESTION, "$1577.00", "x", "  ")[-1]["content"]


def test_strip_citations_handles_lists_and_runs() -> None:
    assert strip_citations("It rose [1, 2] to $5 [3][4].") == "It rose to $5."


def test_figures_skip_names_years_and_quarters() -> None:
    text = "3M's FY2022 sales were $32,765 million in 2022 (Q3: 1.9x, up 12.5%) as of Jun'23."

    assert [f.text for f in figures(text)] == ["32,765", "1.9x", "12.5%"]


def test_distance_allows_for_scale_and_percent_notation() -> None:
    reference = Figure("8.70", 8.70, percent=False)

    assert distance(reference, Figure("8,738", 8738.0, percent=False)) == pytest.approx(
        0.0044, abs=1e-4
    )
    assert distance(Figure("25%", 25.0, True), Figure("0.25", 0.25, False)) == pytest.approx(0.0)
    assert distance(Figure("25%", 25.0, True), Figure("30%", 30.0, True)) == pytest.approx(0.2)


def test_comparisons_pair_each_reference_figure_with_the_closest() -> None:
    pairs = closest_figures("No: 0.96, below 1x, and 0.96 again.", "It was 0.847, near 1.0.")

    assert [(ref.text, close.text if close else None) for ref, close, _ in pairs] == [
        ("0.96", "1.0"),
        ("1x", "1.0"),
    ]
    assert (
        comparisons("Yes.", "It rose 5%.")
        == "Computed comparisons: the reference gives no figures."
    )
    assert "the candidate gives no figures" in comparisons("$1577.00", "It went up.")


def test_a_refusal_needs_no_judge_call() -> None:
    fake = FakeLLM([])

    refused = judge(fake, QUESTION, "$1577.00", "", answered=False)
    empty = judge(fake, QUESTION, "$1577.00", " [1] ")

    assert (refused.verdict, empty.verdict) == ("refused", "refused")
    assert fake.calls == []


def test_the_judge_asks_the_fast_model_for_json_and_reads_the_verdict() -> None:
    fake = FakeLLM(['```json\n{"verdict": "correct", "reason": "Same figure."}\n```'])

    result = judge(fake, QUESTION, "$1577.00", "Capex was $1,577 million [3].")

    assert (result.verdict, result.reason) == ("correct", "Same figure.")
    assert fake.calls[0].role == "fast"
    assert fake.calls[0].extra["response_format"] == {"type": "json_object"}


def test_an_unreadable_verdict_counts_against_the_answer() -> None:
    result = judge(FakeLLM(["I think it is right."]), QUESTION, "$1577.00", "$1,577 million")
    odd = judge(
        FakeLLM([json.dumps({"verdict": "partly"})]), QUESTION, "$1577.00", "$1,577 million"
    )

    assert result.verdict == "incorrect"
    assert result.error is not None
    assert odd.verdict == "incorrect"
    assert odd.error is not None
    with pytest.raises(ValueError, match="valid verdict"):
        parse_verdict('{"reason": "no verdict"}')
