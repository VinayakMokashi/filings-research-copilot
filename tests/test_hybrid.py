"""Hybrid answers: the data agent's figures and the doc agent's pages in one cited answer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from copilot.answer.agent import DocAgent
from copilot.answer.hybrid import DATABASE, FIGURES_HINT, HybridAgent, database_source
from copilot.config import Settings
from copilot.llm import FakeLLM, LLMClient, LLMError, Message, ModelRole
from copilot.llm.base import LLMResponse
from copilot.retrieval.query import CompanyMatcher, Filing
from copilot.retrieval.search import Hit, Searcher
from copilot.sql.agent import build_pipeline
from copilot.sql.tool import DataAgent, DataAnswer

SCHEMA = """
CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL);
CREATE TABLE annual_values (cik INTEGER, metric TEXT, fiscal_year INTEGER, value REAL);
CREATE TABLE metrics (metric TEXT PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO companies VALUES (1, 'ACME', 'Acme');
INSERT INTO annual_values VALUES
    (1, 'capital_expenditure', 2021, 900000000),
    (1, 'capital_expenditure', 2022, 1200000000);
INSERT INTO metrics VALUES ('capital_expenditure', 'Capital expenditure');
"""
SQL = (
    "SELECT fiscal_year, value AS capital_expenditure FROM annual_values "
    "WHERE metric = 'capital_expenditure' ORDER BY fiscal_year"
)
ANSWERABLE = '{"tables": ["annual_values"], "answerable": true}'
DECLINED = '{"tables": [], "answerable": false, "reason": "No such figures."}'
PAGE = "Acme spent more on new plants in fiscal 2022 to meet demand."
QUESTION = "How did Acme's capital expenditure change from 2021 to 2022, and why?"


class _Pages:
    """A searcher that finds the same page whatever the query."""

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 20,
        doc_names: Sequence[str] | None = None,
        *,
        passage: bool = False,
    ) -> list[Hit]:
        return [Hit("p1", 1.0, "ACME_2022_10K", 0, (40,), "7", PAGE, tokens=15)]


class _Refusing:
    """A client whose daily quota is used up."""

    def complete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        raise LLMError("daily limit", rate_limited=True)

    async def acomplete(self, messages: Sequence[Message], **kwargs: object) -> LLMResponse:
        raise LLMError("daily limit", rate_limited=True)


@pytest.fixture
def facts_db(tmp_path: Path) -> Path:
    path = tmp_path / "facts.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


def _sql_models(selection: str) -> FakeLLM:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        return selection if role == "fast" else f"```sql\n{SQL}\n```"

    return FakeLLM(reply)


def _hybrid(facts_db: Path, data_llm: LLMClient, answer: str) -> tuple[HybridAgent, FakeLLM]:
    writer = FakeLLM([answer])
    doc = DocAgent(
        cast(Searcher, _Pages()),
        CompanyMatcher(["Acme"], {"Acme": None}),
        [Filing("ACME_2022_10K", "Acme", "10k", 2022)],
        writer,
        rewrites=(),
    )
    data = DataAgent(build_pipeline(Settings(), data_llm, db_path=facts_db))
    return HybridAgent(doc, data), writer


def _reply(text: str) -> str:
    return json.dumps({"answerable": True, "answer": text, "calculations": [], "missing": ""})


def test_a_hybrid_answer_cites_the_query_result_and_the_pages(facts_db: Path) -> None:
    text = (
        "Acme's capital expenditure rose from $900 million in fiscal 2021 to $1,200 million "
        "in fiscal 2022 [1]. It spent more on new plants to meet demand [2]."
    )
    agent, writer = _hybrid(facts_db, _sql_models(ANSWERABLE), _reply(text))

    result = agent.answer(QUESTION)

    assert result.answer.text == text
    assert (result.database_cited, result.pages_cited) == (True, True)
    first, page = result.answer.sources
    assert (first.number, first.doc_name, page.number, page.doc_name) == (
        1,
        DATABASE,
        2,
        "ACME_2022_10K",
    )
    assert "SELECT fiscal_year" in first.text
    assert "2022 | 1,200,000,000" in first.text
    assert FIGURES_HINT in result.data.hints
    prompt = writer.calls[0].messages[1]["content"]
    assert prompt.index("[1] Facts database") < prompt.index("[2] Acme")


def test_without_a_query_result_the_pages_are_numbered_from_one(facts_db: Path) -> None:
    text = "Acme spent more on new plants in fiscal 2022 to meet demand [1]."
    agent, _ = _hybrid(facts_db, _sql_models(DECLINED), _reply(text))

    result = agent.answer(QUESTION)

    assert result.data.status == "unanswerable"
    assert [(s.number, s.doc_name) for s in result.answer.sources] == [(1, "ACME_2022_10K")]
    assert (result.database_cited, result.pages_cited) == (False, True)


def test_a_used_up_quota_stops_before_the_answer_call(facts_db: Path) -> None:
    agent, writer = _hybrid(facts_db, _Refusing(), _reply("unused"))

    with pytest.raises(LLMError) as caught:
        agent.answer(QUESTION)

    assert caught.value.rate_limited
    assert writer.calls == []


def test_the_query_result_reads_as_a_table() -> None:
    answer = DataAnswer(
        question="q",
        status="ok",
        answer="3 rows.",
        sql="SELECT 1",
        columns=["fiscal_year", "capex", "ratio"],
        rows=[[2021, 900000000.0, 0.012345678], [2022, 1200000000.0, 0.5], [2023, 1.0, 1.0]],
    )

    source = database_source(answer, max_rows=2)

    assert source is not None
    assert source.text.endswith(
        "Result, 3 rows (the first 2 shown):\n"
        "fiscal_year | capex | ratio\n2021 | 900,000,000 | 0.0123457\n2022 | 1,200,000,000 | 0.5"
    )
    declined = DataAnswer(question="q", status="unanswerable", answer="No prices.")
    assert database_source(declined) is None
