"""The data agent as a tool: exact statistics and a typed, serialisable answer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from copilot.config import Settings
from copilot.llm import FakeLLM, Message, ModelRole
from copilot.sql.agent import build_pipeline
from copilot.sql.tool import DataAgent, DataAnswer, column_statistics

SCHEMA = """
CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL);
CREATE TABLE annual_values (cik INTEGER, metric TEXT, fiscal_year INTEGER, value REAL);
CREATE TABLE metrics (metric TEXT PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO companies VALUES (66740, 'MMM', '3M'), (21344, 'KO', 'Coca-Cola');
INSERT INTO annual_values VALUES
    (66740, 'capital_expenditure', 2018, 1577000000),
    (21344, 'capital_expenditure', 2018, 1548000000);
INSERT INTO metrics VALUES ('capital_expenditure', 'Capital expenditure');
"""
BY_COMPANY = (
    "SELECT c.name, a.value / 1e6 AS capex FROM annual_values AS a JOIN companies AS c "
    "USING (cik) WHERE a.fiscal_year = 2018 ORDER BY capex DESC"
)


@pytest.fixture
def facts_db(tmp_path: Path) -> Path:
    path = tmp_path / "facts.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


def _agent(facts_db: Path, selection: str) -> DataAgent:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        if role == "strong":
            return f"```sql\n{BY_COMPANY}\n```"
        if "which tables are needed" in messages[0]["content"]:
            return selection
        return json.dumps(
            {"answer": "3M spent the most.", "insights": ["Close race."], "caveats": []}
        )

    return DataAgent(build_pipeline(Settings(), FakeLLM(reply), db_path=facts_db))


def test_statistics_are_exact_and_name_the_extremes() -> None:
    columns = ["company", "capex", "flag", "note"]
    rows: list[list[Any]] = [
        ["3M", 1577.0, True, None],
        ["Coca-Cola", 1548.0, False, None],
        ["X", None, True, None],
    ]

    (capex,) = column_statistics(columns, rows)

    assert (capex.column, capex.count, capex.total, capex.mean) == ("capex", 2, 3125.0, 1562.5)
    assert (capex.min, capex.min_at, capex.max, capex.max_at) == (1548.0, "Coca-Cola", 1577.0, "3M")
    assert column_statistics(["value"], [[7]])[0].max_at is None


def test_years_and_keys_label_rows_rather_than_count_as_measures() -> None:
    columns = ["cik", "fiscal_year", "capex", "change_id"]
    rows = [[66740, 2018, 1577.0, 1], [66740, 2022, 1749.0, 2]]

    (capex,) = column_statistics(columns, rows)

    assert capex.column == "capex"
    assert (capex.min_at, capex.max_at) == ("2018", "2022")


def test_an_answer_carries_rows_sql_statistics_chart_and_text(facts_db: Path) -> None:
    agent = _agent(facts_db, '{"tables": ["annual_values", "companies"], "answerable": true}')

    answer = agent.ask("Who spent more on capex in 2018, 3M or Coke?")

    assert answer.ok
    assert answer.answer == "3M spent the most."
    assert answer.insights == ["Close race."]
    assert answer.columns == ["name", "capex"]
    assert answer.rows == [["3M", 1577.0], ["Coca-Cola", 1548.0]]
    assert answer.statistics[0].max_at == "3M"
    assert answer.chart is not None
    assert answer.chart.kind == "bar"
    assert answer.sql is not None
    assert answer.sql.startswith("SELECT c.name")
    assert any(hint.startswith('"Coca-Cola" is companies.name') for hint in answer.hints)
    assert DataAnswer.model_validate_json(answer.model_dump_json()) == answer


def test_a_decline_is_a_status_with_the_reason(facts_db: Path) -> None:
    agent = _agent(facts_db, '{"tables": [], "answerable": false, "reason": "No prices."}')

    answer = agent.ask("What is 3M's share price?", analyze=False)

    assert answer.status == "unanswerable"
    assert answer.answer == "No prices."
    assert (answer.rows, answer.statistics, answer.chart, answer.sql) == ([], [], None, None)
