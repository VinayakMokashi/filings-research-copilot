"""The data agent as a tool: one question in, a typed answer out (step 4.4).

The orchestrator (Phase 5), the API and the MCP server (Phase 6) need the data agent's
result in a form they can check, store and send: whether it answered, the SQL that ran,
the rows, exact statistics computed from them, a chart that suits them, and the written
answer. `DataAgent.ask` runs text2sql-analyst's pipeline and returns a `DataAnswer`, a
pydantic model of this project's own, so callers depend on this contract rather than on
the library's internal classes.

Statistics are computed here, from the rows, for every measure column: the count, total,
mean, smallest and largest value, and the row labels of the extremes. They are exact, so
the orchestrator can quote them without a model doing arithmetic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from text2sql.analysis.columns import is_id_column, measure_columns
from text2sql.pipeline import Pipeline, PipelineResult

from copilot.config import Settings
from copilot.llm import LLMClient
from copilot.sql.agent import build_pipeline

Status = Literal["ok", "unanswerable", "error"]
KEYS = {"cik"}  # the facts database's company key: a number, never a measure


class ColumnStatistics(BaseModel):
    """Exact statistics for one numeric column of the result."""

    model_config = ConfigDict(frozen=True)

    column: str
    count: int
    total: float
    mean: float
    min: float
    max: float
    min_at: str | None = None  # the label of the row with the smallest value
    max_at: str | None = None


class Chart(BaseModel):
    """How to draw the result: one figure, bars by category, or a line over time."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["metric", "bar", "line"]
    y: str
    x: str | None = None


class DataAnswer(BaseModel):
    """What the data agent found for one question."""

    model_config = ConfigDict(frozen=True)

    question: str
    status: Status
    answer: str  # the written answer, or why it declined or failed
    insights: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    truncated: bool = False
    statistics: list[ColumnStatistics] = Field(default_factory=list)
    chart: Chart | None = None
    tables: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    attempts: int = 0
    rate_limited: bool = False
    timings: dict[str, float] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _cell(value: Any) -> Any:
    """A value as JSON can carry it: bytes become hex, everything else stays as it is."""
    return value.hex() if isinstance(value, bytes | bytearray) else value


def column_statistics(
    columns: Sequence[str], rows: Sequence[Sequence[Any]]
) -> list[ColumnStatistics]:
    """Statistics for every measure column of a result.

    Measures are the numeric columns that are neither identifiers nor periods, by
    text2sql-analyst's rules (so a fiscal year is a label, not a number to add up); the
    facts database's company key, cik, is an identifier too. The first other column
    labels the rows, for `min_at` and `max_at`.
    """
    if not rows:
        return []
    frame = pd.DataFrame([list(row) for row in rows], columns=list(columns))
    measures = {str(c) for c in measure_columns(frame)} - KEYS
    labels = [
        i
        for i, c in enumerate(columns)
        if c not in measures and not is_id_column(c) and c not in KEYS
    ]
    label = labels[0] if labels else None
    statistics = []
    for index, column in enumerate(columns):
        if column not in measures:
            continue
        values = [(float(row[index]), row) for row in rows if row[index] is not None]
        values = [(number, row) for number, row in values if not math.isnan(number)]
        if not values:
            continue
        smallest = min(values, key=lambda pair: pair[0])
        largest = max(values, key=lambda pair: pair[0])
        total = math.fsum(number for number, _ in values)
        several = label is not None and len(values) > 1
        statistics.append(
            ColumnStatistics(
                column=column,
                count=len(values),
                total=total,
                mean=total / len(values),
                min=smallest[0],
                max=largest[0],
                min_at=str(smallest[1][label]) if several and label is not None else None,
                max_at=str(largest[1][label]) if several and label is not None else None,
            )
        )
    return statistics


def to_answer(result: PipelineResult) -> DataAnswer:
    """text2sql-analyst's result as this project's `DataAnswer`."""
    query = result.result
    columns = list(query.columns) if query else []
    rows = [[_cell(value) for value in row] for row in query.rows] if query else []
    analysis = result.analysis
    if result.status == "ok":
        answer = analysis.answer if analysis else f"{len(rows)} rows."
    else:
        answer = result.message
    chart = result.chart
    return DataAnswer(
        question=result.question,
        status=result.status,
        answer=answer,
        insights=list(analysis.insights) if analysis else [],
        caveats=list(analysis.caveats) if analysis else [],
        sql=result.sql,
        columns=columns,
        rows=rows,
        truncated=bool(query and query.truncated),
        statistics=column_statistics(columns, rows) if rows else [],
        chart=Chart(kind=chart.kind, y=chart.y, x=chart.x) if chart else None,
        tables=list(result.tables_used),
        hints=list(result.hints),
        attempts=len(result.attempts),
        rate_limited=result.rate_limited,
        timings={stage: round(seconds, 4) for stage, seconds in result.timings.items()},
    )


class DataAgent:
    """The data agent: questions about reported figures, answered with read-only SQL."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline

    @classmethod
    def build(cls, settings: Settings, client: LLMClient | None = None) -> DataAgent:
        return cls(build_pipeline(settings, client))

    def ask(self, question: str, *, analyze: bool = True, hints: Sequence[str] = ()) -> DataAnswer:
        """Answer one question; failures come back as a status, never as an exception."""
        return to_answer(self.pipeline.ask(question, analyze=analyze, hints=hints))
