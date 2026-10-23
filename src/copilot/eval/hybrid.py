"""The hybrid question set: questions that need figures and an explanation (step 4.6).

eval/hybrid/questions.jsonl holds ten questions written for this project, each about one dev
company and one of its filings in the corpus, such as "How did 3M's capital expenditure
change from 2017 to 2018, and what did the company say it was investing in?". Each lists:

- the figures a right answer gives: a formula over the company's annual values
  (`capital_expenditure[2018]`), with the restated figure counting too where it is marked;
  or, for a figure the database doesn't hold, its value and where the filing states it;
- what the explanation should address, for reading the answers by hand.

The figure check is mechanical and matches the answer judge's comparisons: a figure counts as
given when a number in the answer is within 1% of it, allowing for thousands, millions and
billions. No FinanceBench text is involved, so the questions and answers are committed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from copilot.eval.judge import Figure, distance, figures
from copilot.facts.formula import Lookup, evaluate

QUESTIONS = Path("eval/hybrid/questions.jsonl")
TOLERANCE = 0.01


class ExpectedFigure(BaseModel):
    """One figure a right answer gives."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    formula: str | None = None  # over the company's annual values
    value: float | None = None  # for a figure the database doesn't hold
    source: str | None = None  # where the filing states that value
    restated: bool = False  # the restated figure (latest_value) counts as well

    @model_validator(mode="after")
    def _one_kind(self) -> ExpectedFigure:
        if (self.formula is None) == (self.value is None):
            raise ValueError(f"{self.name}: give a formula or a value, not both or neither")
        return self


class HybridQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    company: str
    filing: str
    question: str
    figures: list[ExpectedFigure]
    explain: str
    note: str = ""


def load_questions(path: Path = QUESTIONS) -> list[HybridQuestion]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [HybridQuestion.model_validate_json(line) for line in lines if line.strip()]


def _lookup(
    conn: sqlite3.Connection, company: str, column: Literal["value", "latest_value"]
) -> Lookup:
    def lookup(metric: str, year: int) -> float:
        row = conn.execute(
            f"SELECT a.{column} FROM annual_values AS a JOIN companies AS c USING (cik) "
            "WHERE c.name = ? AND a.metric = ? AND a.fiscal_year = ?",
            (company, metric, year),
        ).fetchone()
        if row is None:
            raise LookupError(f"no {metric} for {company} in fiscal {year}")
        return float(row[0])

    return lookup


def expected_values(question: HybridQuestion, conn: sqlite3.Connection) -> list[list[float]]:
    """For each expected figure, the values that count: as first reported, and restated."""
    values = []
    for figure in question.figures:
        accepted: list[float] = []
        if figure.formula is not None:
            accepted.append(evaluate(figure.formula, _lookup(conn, question.company, "value")))
            if figure.restated:
                latest = evaluate(figure.formula, _lookup(conn, question.company, "latest_value"))
                if latest not in accepted:
                    accepted.append(latest)
        elif figure.value is not None:
            accepted.append(figure.value)
        values.append(accepted)
    return values


def gives(text: str, accepted: Sequence[float], tolerance: float = TOLERANCE) -> bool:
    """Whether a number in `text` is within `tolerance` of any accepted value, at any scale."""
    candidates = figures(text)
    return any(
        distance(Figure("", value, percent=False), candidate) <= tolerance
        for value in accepted
        for candidate in candidates
    )
