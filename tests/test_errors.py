"""Sorting answers that went wrong into error categories."""

from __future__ import annotations

from copilot.eval.errors import CATEGORIES, categorise, unfilled


def test_refusals_split_on_whether_the_evidence_was_retrieved() -> None:
    assert categorise("refused", context_hit=True, calculation_failed=False) == (
        "refused, evidence retrieved"
    )
    assert categorise("refused", context_hit=False, calculation_failed=True) == (
        "refused, evidence not retrieved"
    )


def test_wrong_answers_check_calculations_before_retrieval() -> None:
    assert categorise("incorrect", context_hit=False, calculation_failed=True) == (
        "calculation broke"
    )
    assert categorise(
        "incorrect", context_hit=True, calculation_failed=False, text="{c1*100}%"
    ) == ("calculation broke")
    assert categorise("incorrect", context_hit=False, calculation_failed=False) == (
        "evidence not retrieved"
    )
    assert categorise("incorrect", context_hit=True, calculation_failed=False) == (
        "wrong with the evidence in context"
    )
    assert categorise("correct", context_hit=False, calculation_failed=True) == "correct"


def test_unfilled_placeholders_and_failures_are_spotted() -> None:
    assert unfilled("It was {c1*100}% in 2022.")
    assert unfilled("Margin was [calculation failed].")
    assert not unfilled("Margin was 19.1% in fiscal 2022 [2].")
    assert len(CATEGORIES) == len(set(CATEGORIES)) == 6
