"""The data agent: text2sql-analyst's pipeline on the gateway, over a facts-shaped database."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest
from text2sql.llm import LLMError as Text2SQLError

from copilot.config import Settings
from copilot.llm import FakeLLM, LLMError, Message, ModelRole
from copilot.llm.base import LLMResponse
from copilot.sql.adapter import GatewayLLM
from copilot.sql.agent import build_pipeline

SCHEMA = """
CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL);
CREATE TABLE annual_values (
    cik INTEGER NOT NULL REFERENCES companies(cik),
    metric TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    value REAL
);
CREATE TABLE metrics (metric TEXT PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO companies VALUES (66740, 'MMM', '3M'), (21344, 'KO', 'Coca-Cola');
INSERT INTO metrics VALUES ('capital_expenditure', 'Capital expenditure'), ('revenue', 'Revenue');
INSERT INTO annual_values VALUES
    (66740, 'capital_expenditure', 2018, 1577000000),
    (21344, 'capital_expenditure', 2018, 1548000000);
"""
SQL = "SELECT a.value / 1e6 FROM annual_values AS a JOIN companies AS c USING (cik) " + (
    "WHERE c.name = '3M' AND a.metric = 'capital_expenditure' AND a.fiscal_year = 2018"
)


@pytest.fixture
def facts_db(tmp_path: Path) -> Path:
    path = tmp_path / "facts.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


def _models(selection: str, sql: str) -> FakeLLM:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        return selection if role == "fast" else f"```sql\n{sql}\n```"

    return FakeLLM(reply)


def test_gateway_llm_maps_roles_and_messages() -> None:
    fake = FakeLLM(["SELECT 1"])

    reply = GatewayLLM(fake, "sql").complete("You write SQL.", "Question: one", max_tokens=50)

    assert reply.text == "SELECT 1"
    call = fake.calls[0]
    assert call.role == "strong"
    assert [m["role"] for m in call.messages] == ["system", "user"]
    assert call.messages[1]["content"] == "Question: one"


class _Refusing:
    """A client whose daily quota is used up."""

    def complete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        raise LLMError("daily limit", rate_limited=True)

    async def acomplete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        raise LLMError("daily limit", rate_limited=True)


def test_gateway_errors_become_text2sql_errors_and_keep_the_quota_flag() -> None:
    with pytest.raises(Text2SQLError) as caught:
        GatewayLLM(_Refusing(), "helper").complete("s", "u")

    assert caught.value.rate_limited


def test_the_pipeline_answers_over_a_facts_database(facts_db: Path) -> None:
    fake = _models('{"tables": ["annual_values", "companies"], "answerable": true}', SQL)
    pipeline = build_pipeline(
        Settings(), fake, db_path=facts_db, descriptions={"companies": "One row per company."}
    )

    out = pipeline.ask("What was 3M's FY2018 capex in millions?", analyze=False, hints=["3M"])

    assert out.ok, out.message
    assert out.result is not None
    assert out.result.rows == [(1577.0,)]
    assert out.tables_used == ["annual_values", "companies"]
    assert {call.role for call in fake.calls} == {"fast", "strong"}
    selection_prompt = fake.calls[0].messages[1]["content"]
    assert "Description: One row per company." in selection_prompt
    sql_prompt = fake.calls[1].messages[1]["content"]
    assert "\"3M\" is companies.name = '3M' (cik 66740)" in sql_prompt
    assert "annual_values.metric takes only these values: capital_expenditure" in sql_prompt
    assert out.hints[-1] == "3M"


def test_the_pipeline_declines_what_the_tables_cannot_answer(facts_db: Path) -> None:
    fake = _models('{"tables": [], "answerable": false, "reason": "No prices."}', SQL)
    pipeline = build_pipeline(Settings(), fake, db_path=facts_db, descriptions={}, linking=False)

    out = pipeline.ask("What is 3M's share price today?", analyze=False)

    assert out.status == "unanswerable"
    assert out.message == "No prices."
    assert not any(call.role == "strong" for call in fake.calls)
