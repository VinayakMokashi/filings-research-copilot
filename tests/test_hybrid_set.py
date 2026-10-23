"""The hybrid question set and its figure check."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from copilot.eval.hybrid import (
    ExpectedFigure,
    HybridQuestion,
    expected_values,
    gives,
    load_questions,
)
from copilot.facts.formula import lookups

SPLITS = Path("eval/financebench/splits.json")


def test_the_committed_set_holds_ten_dev_questions_with_valid_formulas() -> None:
    questions = load_questions()
    held_out = set(json.loads(SPLITS.read_text(encoding="utf-8"))["test_companies"])

    assert [q.id for q in questions] == [f"h{n:02d}" for n in range(1, 11)]
    assert not {q.company for q in questions} & held_out
    for question in questions:
        assert question.filing.upper().startswith(question.company.upper().split()[0][:4])
        for figure in question.figures:
            if figure.formula is not None:
                assert lookups(figure.formula)


def test_expected_values_take_first_reported_and_restated_figures() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE companies (cik INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE annual_values (cik INTEGER, metric TEXT, fiscal_year INTEGER,
                                    value REAL, latest_value REAL);
        INSERT INTO companies VALUES (1, 'Acme');
        INSERT INTO annual_values VALUES (1, 'revenue', 2017, 93.0, 94.0),
                                         (1, 'revenue', 2018, 101.0, 101.0);
        """
    )
    question = HybridQuestion(
        id="h99",
        company="Acme",
        filing="ACME_2018_10K",
        question="How did Acme's revenue change?",
        figures=[
            ExpectedFigure(name="2017", formula="revenue[2017]", restated=True),
            ExpectedFigure(name="change", formula="revenue[2018] - revenue[2017]"),
            ExpectedFigure(name="segment", value=25.0, source="ACME_2018_10K, PDF page 3"),
        ],
        explain="why",
    )

    assert expected_values(question, conn) == [[93.0, 94.0], [8.0], [25.0]]


def test_a_figure_is_given_at_any_scale_within_one_percent() -> None:
    capex = [1577e6]

    assert gives("Capital expenditure was $1,577 million in 2018.", capex)
    assert gives("It spent $1.58 billion.", capex)
    assert not gives("It spent $1.6 billion.", capex)
    assert not gives("It spent more in 2018 than in 2017.", capex)
    assert gives("Revenue was $93,392 million, or $94,005 million restated.", [94005e6])


def test_a_figure_needs_a_formula_or_a_value_but_not_both() -> None:
    with pytest.raises(ValidationError):
        ExpectedFigure(name="neither")
    with pytest.raises(ValidationError):
        ExpectedFigure(name="both", formula="revenue[2018]", value=1.0)
