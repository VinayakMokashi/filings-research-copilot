"""Hybrid answers, version 2: routing by need, the planner's split, partial answers, retries."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from copilot.answer.agent import DocAgent
from copilot.answer.hybrid import DATABASE, FIGURES_HINT
from copilot.answer.hybrid_v2 import SYSTEM_PROMPT, HybridAgentV2, make_plan, one_filing
from copilot.config import Settings
from copilot.llm import FakeLLM, LLMClient, LLMError, Message, ModelRole
from copilot.llm.base import LLMResponse
from copilot.retrieval.query import CompanyMatcher, Filing
from copilot.retrieval.search import Hit, Searcher
from copilot.sql.agent import build_pipeline
from copilot.sql.tool import DataAgent

SCHEMA = """
CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL);
CREATE TABLE annual_values (cik INTEGER, metric TEXT, fiscal_year INTEGER, value REAL);
CREATE TABLE metrics (metric TEXT PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO companies VALUES (1, 'ACME', 'Acme');
INSERT INTO annual_values VALUES
    (1, 'capital_expenditure', 2018, 700000000),
    (1, 'capital_expenditure', 2022, 1200000000);
INSERT INTO metrics VALUES ('capital_expenditure', 'Capital expenditure');
"""
SQL = (
    "SELECT fiscal_year, value AS capital_expenditure FROM annual_values "
    "WHERE metric = 'capital_expenditure' ORDER BY fiscal_year"
)
ANSWERABLE = '{"tables": ["annual_values"], "answerable": true}'
PAGE = "Acme spent more on new plants in fiscal 2022 to meet demand."
TWO_YEARS = "How did Acme's capital expenditure change from 2021 to 2022, and why?"
FIVE_YEARS = "How did Acme's capital expenditure change from 2018 to 2022, and why?"
PLAN = json.dumps(
    {
        "figures": "What was Acme's capital expenditure in each fiscal year from 2018 to 2022?",
        "reasons": "What does Acme's 2022 10-K say drove its capital expenditure?",
    }
)
FILINGS = [
    Filing("ACME_2022_10K", "Acme", "10k", 2022),
    Filing("ACME_2021_10Q", "Acme", "10q", 2021, quarter=2),
]


class _Pages:
    """A searcher that finds the same page whatever the query, and records the queries."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 20,
        doc_names: Sequence[str] | None = None,
        *,
        passage: bool = False,
    ) -> list[Hit]:
        self.queries.append(query)
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


def _sql_models() -> FakeLLM:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        return ANSWERABLE if role == "fast" else f"```sql\n{SQL}\n```"

    return FakeLLM(reply)


def _answer(text: str, *, answerable: bool = True, missing: str = "") -> str:
    reply = {"answerable": answerable, "answer": text, "calculations": [], "missing": missing}
    return json.dumps(reply)


def _agent(
    facts_db: Path, replies: Sequence[str], data_llm: LLMClient | None = None
) -> tuple[HybridAgentV2, FakeLLM, _Pages]:
    writer, pages = FakeLLM(list(replies)), _Pages()
    doc = DocAgent(
        cast(Searcher, pages),
        CompanyMatcher(["Acme"], {"Acme": None}),
        FILINGS,
        writer,
        rewrites=(),
    )
    data = DataAgent(build_pipeline(Settings(), data_llm or _sql_models(), db_path=facts_db))
    return HybridAgentV2(doc, data), writer, pages


def _doc() -> DocAgent:
    return DocAgent(
        cast(Searcher, _Pages()), CompanyMatcher(["Acme"], {"Acme": None}), FILINGS, FakeLLM([])
    )


@pytest.mark.parametrize(
    ("question", "filing"),
    [
        (TWO_YEARS, "ACME_2022_10K"),
        ("What was Acme's capital expenditure in fiscal 2022, and why?", "ACME_2022_10K"),
        (FIVE_YEARS, None),  # more years than one 10-K compares
        ("Why did Acme's capital expenditure rise?", None),  # no year named
        ("How did Acme's capex change from 2020 to 2021?", None),  # no 10-K for 2021
        ("What did Acme spend in Q2 2021, and why?", None),  # a quarter
    ],
)
def test_one_filing_finds_the_10k_that_states_every_year(question: str, filing: str | None) -> None:
    assert one_filing(question, _doc()) == filing


def test_a_question_one_filing_answers_goes_to_the_doc_agent_alone(facts_db: Path) -> None:
    text = "Acme spent more on new plants in fiscal 2022 to meet demand [1]."
    agent, writer, _ = _agent(facts_db, [_answer(text)])

    result = agent.answer(TWO_YEARS)

    assert result.path == "doc"
    assert result.data is None
    assert result.answer.text == text
    assert len(writer.calls) == 1  # the doc agent's answer call; no plan
    assert "Facts database" not in writer.calls[0].messages[0]["content"]


def test_a_split_question_gives_each_agent_its_part(facts_db: Path) -> None:
    text = (
        "Acme's capital expenditure rose from $700 million in fiscal 2018 to $1,200 million "
        "in fiscal 2022 [1]. It spent more on new plants to meet demand [2]."
    )
    agent, writer, pages = _agent(facts_db, [PLAN, _answer(text)])

    result = agent.answer(FIVE_YEARS)

    assert result.path == "split"
    plan = json.loads(PLAN)
    assert (result.figures_question, result.reasons_question) == (plan["figures"], plan["reasons"])
    assert result.data is not None
    assert result.data.question == plan["figures"]
    assert FIGURES_HINT not in result.data.hints  # the planner's question replaces the hint
    assert pages.queries == [plan["reasons"]]
    assert [(s.number, s.doc_name) for s in result.answer.sources] == [
        (1, DATABASE),
        (2, "ACME_2022_10K"),
    ]
    assert writer.calls[1].messages[0]["content"] == SYSTEM_PROMPT
    assert result.answer.text == text
    assert not result.retried


def test_a_partial_answer_is_retried_with_a_wider_search(facts_db: Path) -> None:
    partial = _answer(
        "Acme's capital expenditure was $1,200 million in fiscal 2022 [1].",
        missing="what drove the change",
    )
    full = _answer("Acme spent more on new plants to meet demand [2].")
    agent, writer, pages = _agent(facts_db, [PLAN, partial, full])

    result = agent.answer(FIVE_YEARS)

    assert result.retried
    assert result.first is not None
    assert result.first.missing == "what drove the change"
    assert result.answer.text == "Acme spent more on new plants to meet demand [2]."
    assert pages.queries[-1] == "what drove the change"  # the retry's extra search
    assert len(writer.calls) == 3


def test_a_partial_answer_stands_when_the_retry_refuses(facts_db: Path) -> None:
    text = "Acme's capital expenditure was $1,200 million in fiscal 2022 [1]."
    partial = _answer(text, missing="what drove the change")
    refusal = _answer("", answerable=False, missing="the reasons")
    agent, _, _ = _agent(facts_db, [PLAN, partial, refusal])

    result = agent.answer(FIVE_YEARS)

    assert result.answer.text == text
    assert result.answer.answerable
    assert result.retried


def test_an_unreadable_plan_keeps_the_whole_question() -> None:
    plan = make_plan(FakeLLM(["not JSON"]), FIVE_YEARS)

    assert (plan.figures, plan.reasons) == (FIVE_YEARS, FIVE_YEARS)
    assert plan.error is not None


def test_a_used_up_quota_stops_before_the_answer_call(facts_db: Path) -> None:
    agent, writer, _ = _agent(facts_db, [PLAN, _answer("unused")], data_llm=_Refusing())

    with pytest.raises(LLMError) as caught:
        agent.answer(FIVE_YEARS)

    assert caught.value.rate_limited
    assert len(writer.calls) == 1  # the plan only


def test_the_prompt_allows_partial_answers_and_keeps_arithmetic_with_the_calculator() -> None:
    assert "Answer with whatever part of the question the sources support" in SYSTEM_PROMPT
    assert "only as its placeholder" in SYSTEM_PROMPT
