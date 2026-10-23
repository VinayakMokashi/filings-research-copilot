"""Hybrid answers: figures from the facts database, explanations from the filings (step 4.6).

A question such as "How did 3M's capital expenditure change from 2017 to 2018, and what
did the spending go to?" has two halves. The figures are in the facts database, as
reported; the reasons are only in the filing's text. A hybrid answer asks both agents and
writes one answer from what they found:

1. **Figures.** The data agent answers the question with one more hint: to answer only
   what the database's figures can, so the request for reasons doesn't make it decline.
   Its query result, the SQL with the rows, becomes source [1].
2. **Text.** The doc agent's retrieval finds the filing pages, packed as sources [2], [3]
   and on, within the doc agent's token budget.
3. **One answer.** The answer model writes from all the sources at once, under the doc
   agent's rules (a citation on every sentence, the calculator for arithmetic, a refusal
   when the sources fall short) and two more: figures come from the database source when
   it has them, and a page that states a figure differently, such as a restated one, is
   pointed out rather than ignored.

When the data agent declines or fails, the answer is written from the pages alone. There is
no retry: this is a prototype for the orchestrator (Phase 5), which will route and combine.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from copilot.answer.agent import DocAgent, Retrieval
from copilot.answer.context import BUDGET_TOKENS, Source
from copilot.answer.generate import ROLE, Answer, build_answer
from copilot.llm import LLMError, Message, system, user
from copilot.sql.tool import DataAgent, DataAnswer

DATABASE = "facts-database"  # the doc_name of the query-result source, which has no page
DATABASE_LABEL = "Facts database: a query over XBRL figures as first reported"
FIGURES_HINT = (
    "Other sources will answer any part of this question that asks for reasons, "
    "explanations or commentary. Answer the figures it asks for that the database holds, "
    "and decline only if it holds none of them."
)
MAX_ROWS = 30
PROMPT_VERSION = "1"

SYSTEM_PROMPT = """\
You answer questions about public companies using only the numbered sources provided. \
Source [1], when it is labelled "Facts database", is the result of a query over the \
figures companies report in their SEC filings (XBRL data, as first reported), in the units \
the query gives them: dollars unless the SQL scales them. The other sources are pages from \
the companies' filings.

Rules:
- Use only facts the sources state. Don't use outside knowledge, even when you are sure of it.
- Take figures from the database source when it has them, and use the pages for reasons, \
explanations and context. When a page states a different figure for the same item and \
period, such as a restated one, give both and say which is which.
- End every sentence that states a fact with the numbers of the sources that state it, in \
square brackets, like [1] or [2][5]. An answer without citations is not accepted.
- Don't do arithmetic yourself. When the answer needs a computed number (a ratio, total, \
difference, growth rate or average), add an expression to "calculations" that uses only \
numbers from the sources with + - * / and parentheses, give it an id such as c1 and the \
number of decimals to show, and write {c1} in the answer where the result goes.
- If the sources don't contain what the question needs, set "answerable" to false and name \
in "missing" the facts that are missing, with their line items and periods.
- Answer in at most five sentences, and give the units and fiscal period of every figure.

Return only a JSON object with the keys "answerable" (true or false), "answer" (text whose \
every sentence ends with its citations), "calculations" (a list of objects with "id", \
"expression" and "decimals") and "missing" (text, empty when nothing is missing)."""


def _cell(value: Any) -> str:
    """A result cell as the answer model reads it: large whole numbers with separators."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return str(value)
    if abs(value) >= 10_000:
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return f"{value:.6g}" if isinstance(value, float) else str(value)


def database_source(answer: DataAnswer, number: int = 1, max_rows: int = MAX_ROWS) -> Source | None:
    """The data agent's query result as a numbered source, or None when it has no rows."""
    if not answer.ok or not answer.rows or not answer.sql:
        return None
    shown = answer.rows[:max_rows]
    lines = [" | ".join(answer.columns)]
    lines += [" | ".join(_cell(value) for value in row) for row in shown]
    more = f" (the first {len(shown)} shown)" if len(answer.rows) > len(shown) else ""
    text = f"SQL:\n{answer.sql}\n\nResult, {len(answer.rows)} rows{more}:\n" + "\n".join(lines)
    return Source(
        number=number,
        doc_name=DATABASE,
        page=-1,
        label=DATABASE_LABEL,
        text=text,
        tokens=len(text) // 4,
    )


def hybrid_messages(question: str, sources: Sequence[Source]) -> list[Message]:
    blocks = "\n\n".join(f"[{s.number}] {s.label}\n{s.text}" for s in sources)
    return [system(SYSTEM_PROMPT), user(f"Question: {question}\n\nSources:\n\n{blocks}")]


@dataclass(frozen=True, slots=True)
class HybridAnswer:
    """The answer, the data agent's result behind its figures, and the pages retrieved.

    Version 2 (`copilot.answer.hybrid_v2`) also records which path it took (`split`, both
    agents; `doc`, the doc agent alone, with no data result), the two questions it split
    the question into, and the answer it wrote before a retry, if it retried.
    """

    answer: Answer
    data: DataAnswer | None
    retrieval: Retrieval
    path: str = "split"
    figures_question: str = ""
    reasons_question: str = ""
    first: Answer | None = None

    @property
    def retried(self) -> bool:
        return self.first is not None

    @property
    def database_cited(self) -> bool:
        return any(source.doc_name == DATABASE for source in self.answer.cited_sources)

    @property
    def pages_cited(self) -> bool:
        return any(source.doc_name != DATABASE for source in self.answer.cited_sources)


class HybridAgent:
    """Answers with the data agent's figures and the doc agent's pages; see the module."""

    def __init__(self, doc: DocAgent, data: DataAgent, *, budget: int = BUDGET_TOKENS) -> None:
        self.doc = doc
        self.data = data
        self.budget = budget

    def answer(self, question: str) -> HybridAnswer:
        data = self.data.ask(question, analyze=False, hints=(FIGURES_HINT,))
        if data.rate_limited:
            raise LLMError(data.answer, rate_limited=True)
        retrieval = self.doc.retrieve(question)
        first = database_source(data)
        pages = self.doc.context(retrieval, self.budget)
        start = 2 if first else 1
        sources = [first] if first else []
        sources += [dataclasses.replace(page, number=n) for n, page in enumerate(pages, start)]
        response = self.doc.llm.complete(
            hybrid_messages(question, sources),
            role=ROLE,
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return HybridAnswer(build_answer(question, sources, response), data, retrieval)
