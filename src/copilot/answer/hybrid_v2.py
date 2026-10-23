"""Hybrid answers, version 2: route by need, split the question, answer in part, retry.

The prototype (step 4.6, `copilot.answer.hybrid`) asked both agents the whole question and
refused whenever the pages didn't explain the figures it had. Its report set out what to
change, and this version does it (step 5.1):

1. **Route by need.** A 10-K states its fiscal year's figures beside the year before and
   explains the change, so a question about one company and at most two consecutive
   years, the later of which has a 10-K in the corpus, goes to the doc agent alone, with
   its retry, at about 60% of the cost. Any other question is split.
2. **Split.** A planner call writes two questions: one asking the database for the figures
   only, and one asking the filings for the explanation only. The data agent gets the
   first, so a request for reasons can't make it decline; the doc agent's retrieval gets
   the second.
3. **Answer in part.** One answer call reads the query result as source [1] and the pages
   after it. When the sources give the figures but not their explanation, it answers with
   what they give and names the rest in `missing`, instead of refusing.
4. **Retry.** When something is missing, the pages are searched again for it across all of
   the company's filings, as the doc agent does, and the answer is written again from the
   larger context; an answer beats a refusal.
5. **Arithmetic once.** A computed figure appears only as the calculator's placeholder,
   never also as a number the model wrote.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from copilot.answer.agent import DocAgent
from copilot.answer.context import BUDGET_TOKENS, Source
from copilot.answer.generate import ROLE, Answer, build_answer
from copilot.answer.hybrid import HybridAnswer, database_source
from copilot.llm import LLMClient, LLMError, Message, system, user
from copilot.llm.parsing import json_object
from copilot.retrieval.query import understand
from copilot.sql.tool import DataAgent, DataAnswer

PROMPT_VERSION = "2"

PLAN_PROMPT = """\
You split a question about a public company into the two questions its answer needs. A \
database holds the annual figures companies report in their SEC filings, such as revenue, \
net income, capital expenditure, cash from operations and debt, by company and fiscal year. \
The filings' text holds the explanations.

Write:
- "figures": one question that asks the database for exactly the figures the question \
needs, naming the company, the measures and every fiscal year, and nothing else. Leave it \
empty if the question needs no reported figures.
- "reasons": one question that asks the filings for exactly the explanation or commentary \
the question needs, naming the company and the filing or period. Leave it empty if the \
question asks for no explanation.

Return only a JSON object with the keys "figures" and "reasons"."""

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
number of decimals to show, and write {c1} in the answer where the result goes. Write each \
computed number only as its placeholder, never also as a number of your own.
- Answer with whatever part of the question the sources support. When they give the \
figures but not the explanation, or the other way round, answer with what they give, set \
"answerable" to true, and name the part they don't cover in "missing"; don't write about \
it in the answer. Set "answerable" to false only when the sources support none of the answer.
- Answer in at most five sentences, and give the units and fiscal period of every figure.

Return only a JSON object with the keys "answerable" (true or false), "answer" (text whose \
every sentence ends with its citations), "calculations" (a list of objects with "id", \
"expression" and "decimals") and "missing" (text, empty when nothing is missing)."""


@dataclass(frozen=True, slots=True)
class Plan:
    """The question split in two; a reply that can't be read keeps the whole question."""

    figures: str
    reasons: str
    error: str | None = None


class _PlanReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    figures: str = ""
    reasons: str = ""


def plan_messages(question: str) -> list[Message]:
    return [system(PLAN_PROMPT), user(f"Question: {question}")]


def make_plan(llm: LLMClient, question: str) -> Plan:
    """The figures and reasons questions, from one call on the strong model."""
    response = llm.complete(
        plan_messages(question),
        role=ROLE,
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    try:
        reply = _PlanReply.model_validate(json_object(response.text))
    except ValueError as exc:
        return Plan(figures=question, reasons=question, error=str(exc)[:300])
    return Plan(figures=reply.figures.strip(), reasons=reply.reasons.strip())


def one_filing(question: str, agent: DocAgent) -> str | None:
    """The annual filing that states every year the question names, or None.

    One company, no quarters, and at most two consecutive fiscal years, the later of which
    has a 10-K in the agent's corpus.
    """
    cues = understand(question, agent.matcher)
    if len(cues.companies) != 1 or not cues.years or cues.quarters:
        return None
    latest, earliest = max(cues.years), min(cues.years)
    if latest - earliest > 1:
        return None
    for filing in agent.filings:
        if filing.company == cues.companies[0] and filing.form == "10k" and filing.year == latest:
            return filing.doc_name
    return None


def answer_messages(question: str, sources: Sequence[Source]) -> list[Message]:
    blocks = "\n\n".join(f"[{s.number}] {s.label}\n{s.text}" for s in sources)
    return [system(SYSTEM_PROMPT), user(f"Question: {question}\n\nSources:\n\n{blocks}")]


class HybridAgentV2:
    """Figures and reasons from the agent that holds them; see the module docstring."""

    def __init__(self, doc: DocAgent, data: DataAgent, *, budget: int = BUDGET_TOKENS) -> None:
        self.doc = doc
        self.data = data
        self.budget = budget

    def answer(self, question: str) -> HybridAnswer:
        if one_filing(question, self.doc) is not None:
            alone = self.doc.answer(question)
            return HybridAnswer(alone.answer, None, alone.retrieval, path="doc", first=alone.first)

        plan = make_plan(self.doc.llm, question)
        data: DataAnswer | None = None
        if plan.figures:
            data = self.data.ask(plan.figures, analyze=False)
            if data.rate_limited:
                raise LLMError(data.answer, rate_limited=True)
        reasons = plan.reasons or question
        retrieval = self.doc.retrieve(reasons)
        answer = self._write(question, data, self.doc.context(retrieval, self.budget))
        result = HybridAnswer(
            answer,
            data,
            retrieval,
            path="split",
            figures_question=plan.figures,
            reasons_question=plan.reasons,
        )
        if not answer.missing.strip():
            return result

        documents = self.doc.company_filings(question) or retrieval.filings
        wider = self.doc.retrieve(reasons, documents, missing=answer.missing)
        second = self._write(question, data, self.doc.context(wider, self.doc.retry_budget))
        if second.answerable or not answer.answerable:
            return dataclasses.replace(result, answer=second, retrieval=wider, first=answer)
        return dataclasses.replace(result, first=answer)  # the retry refused; keep the answer

    def _write(self, question: str, data: DataAnswer | None, pages: Sequence[Source]) -> Answer:
        first = database_source(data) if data is not None else None
        sources = [first] if first else []
        start = len(sources) + 1
        sources += [dataclasses.replace(page, number=n) for n, page in enumerate(pages, start)]
        response = self.doc.llm.complete(
            answer_messages(question, sources),
            role=ROLE,
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return build_answer(question, sources, response)
