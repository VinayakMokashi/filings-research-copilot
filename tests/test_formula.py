"""The safe formula evaluator used by the facts cross-checks."""

from __future__ import annotations

import pytest

from copilot.facts.formula import FormulaError, evaluate, lookups

VALUES = {
    ("revenue", 2019): 200.0,
    ("revenue", 2018): 150.0,
    ("ppe", 2018): 10.0,
    ("ppe", 2019): 30.0,
}


def lookup(metric: str, year: int) -> float:
    return VALUES[(metric, year)]


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("1 + 2 * 3", 7.0),
        ("-(4 - 6) / 4", 0.5),
        ("+3", 3.0),
        ("2e3 / 1e3", 2.0),
        ("revenue[2019] / ((ppe[2018] + ppe[2019]) / 2)", 10.0),
        ("(revenue[2019] / revenue[2018] - 1) * 100", pytest.approx(33.333, abs=1e-3)),
    ],
)
def test_arithmetic_and_lookups(formula: str, expected: float) -> None:
    assert evaluate(formula, lookup) == expected


@pytest.mark.parametrize(
    "formula",
    [
        "__import__('os')",
        "revenue",
        "revenue.real",
        "revenue[2019] ** 2",
        "revenue['2019']",
        "True + 1",
        "[1, 2]",
        "1 if 2 else 3",
        "revenue[2019",
    ],
)
def test_anything_else_is_refused(formula: str) -> None:
    with pytest.raises(FormulaError):
        evaluate(formula, lookup)


def test_division_by_zero_is_reported() -> None:
    with pytest.raises(FormulaError, match="zero"):
        evaluate("revenue[2019] / (ppe[2018] - 10)", lookup)


def test_missing_values_propagate_from_the_lookup() -> None:
    with pytest.raises(KeyError):
        evaluate("revenue[2030]", lookup)


def test_lookups_lists_what_a_formula_reads() -> None:
    assert lookups("revenue[2019] / ((ppe[2018] + ppe[2019]) / 2)") == [
        ("revenue", 2019),
        ("ppe", 2018),
        ("ppe", 2019),
    ]
