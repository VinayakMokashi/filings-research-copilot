"""The brief crew (step 7.6): a research brief planned, written in sections, edited, checked.

A request for a brief ("Write a one-page brief on 3M's 2022 results for an investment
committee") asks for several things at once: the results, the segments, the risks, the
balance sheet. One retrieval can't serve them all, because each needs other pages. The crew
splits the work as an analyst would:

1. **Plan** (Self-Discover; Zhou et al., 2024). One strong-model call SELECTs the analysis
   modules the request needs from a fixed list (`MODULES`), ADAPTs each to the company and
   period, and IMPLEMENTs them as two to five sections, each with one standalone question
   and the specialist that should answer it: the doc agent for what the filings' text says,
   the hybrid for figures and the reasons behind them.
2. **Write.** The specialists answer the sections' questions in parallel threads, each with
   its own cited sources; the hybrid's calls go one at a time, since its data agent shares
   one database connection.
3. **Check** (the critic). The validator's checker reads every section's sentences against
   the sources they cite, on the `small` role, and a sentence no source supports is cut
   (`copilot.agents.validator.trim`). A section with nothing left is dropped and named.
4. **Edit.** The sections' sources are numbered again into one list for the brief, and one
   call writes a summary of two or three sentences from the sections' own sentences, citing
   the brief's numbers and adding no fact the sections don't hold. The summary is checked
   and cut the same way.

The brief is Markdown: the title, the summary, then each section's heading and text, with
citations as [n] into the brief's sources; `Brief.citations` lists them as the graph's
answers do.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.agents.validator import check_answer, passes, trim
from copilot.answer.context import Source
from copilot.answer.generate import Answer, citations
from copilot.llm import LLMClient, LLMError, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

PROMPT_VERSION = "1"
PLAN_ROLE: ModelRole = "strong"
EDIT_ROLE: ModelRole = "strong"
MIN_SECTIONS, MAX_SECTIONS = 2, 5

# The analysis modules a plan selects from (Self-Discover's reasoning modules, for briefs).
MODULES: dict[str, str] = {
    "results": "Results: revenue and earnings for the period, and how they changed",
    "segments": "Segments: how each business, product line or region performed",
    "profitability": "Profitability: margins and what moved them",
    "cash_flow": "Cash flow: cash from operations, capital spending and free cash flow",
    "liquidity": "Liquidity and leverage: cash, debt, credit facilities and maturities",
    "capital_returns": "Capital returns: dividends and share repurchases",
    "risks": "Risks: the risk factors and uncertainties management names",
    "legal": "Legal and regulatory matters: litigation, investigations, regulation",
    "outlook": "Outlook: guidance, priorities and plans management states",
    "strategy": "Strategy and competition: the business model, markets and competitors",
    "one_offs": "Unusual items: impairments, restructuring and other one-time charges",
}

Specialist = Literal["doc", "hybrid"]

PLAN_PROMPT = """\
You plan research briefs about US public companies. A brief is written only from the \
companies' SEC filings and the figures they report, by two research assistants: "doc" \
answers from the text of the filings (risks, strategy, legal matters, management's \
explanations, segment detail), and "hybrid" answers with reported figures (revenue, \
earnings, margins, cash flow, debt, dividends, buybacks) together with management's \
explanation of them.

Plan in three steps:
1. SELECT the analysis modules the request needs, from this list:
{modules}
2. ADAPT each selected module to the request: the company, the fiscal period and exactly \
what to find.
3. IMPLEMENT the plan as {low} to {high} sections, one module each, in the order a reader \
needs them. Each section has a short "heading", one standalone "question" for an assistant \
that names the company and the fiscal period, the "route" ("doc" or "hybrid") and the \
"module" it implements.

Cover what the request asks for and nothing else. Use the fiscal period the request names, \
or the latest fiscal year if it names none. Don't plan investment advice or price \
forecasts.

Return only a JSON object with the keys "title" (the brief's title), "modules" (the \
selected module names), "adapted" (one line for each selected module) and "sections" (a \
list of objects with "heading", "question", "route" and "module")."""

EDIT_PROMPT = """\
You edit research briefs. Given a brief's sections, write its summary: two or three \
sentences that state the brief's main findings, for the reader the request names.

Rules:
- Use only facts the sections state, and end every sentence with the citations, in square \
brackets like [3] or [2][5], of the section sentences it rests on.
- Add no figure, fact or judgement the sections don't hold. Don't give investment advice.

Return only a JSON object with the key "summary"."""


class SectionPlan(BaseModel):
    """One section of the plan: what to ask, and whom."""

    model_config = ConfigDict(extra="ignore")

    heading: str = Field(min_length=1)
    question: str = Field(min_length=1)
    route: Specialist = "hybrid"
    module: str = ""


class BriefPlan(BaseModel):
    """The plan: the title, the modules it selected and adapted, and the sections."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    modules: list[str] = Field(default_factory=list)
    adapted: list[str] = Field(default_factory=list)
    sections: list[SectionPlan]


def plan_messages(request: str) -> list[Message]:
    modules = "\n".join(f"- {name}: {text}" for name, text in MODULES.items())
    prompt = PLAN_PROMPT.format(modules=modules, low=MIN_SECTIONS, high=MAX_SECTIONS)
    return [system(prompt), user(f"Request: {request}")]


def parse_plan(text: str) -> BriefPlan:
    """The plan in a model's reply, with at most MAX_SECTIONS sections.

    ValueError when the reply holds no plan or one with fewer than MIN_SECTIONS sections.
    """
    try:
        plan = BriefPlan.model_validate(json_object(text))
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"No plan in the reply: {exc}") from exc
    if len(plan.sections) < MIN_SECTIONS:
        raise ValueError(f"The plan has {len(plan.sections)} sections, fewer than {MIN_SECTIONS}.")
    return plan.model_copy(update={"sections": plan.sections[:MAX_SECTIONS]})


def fallback_plan(request: str) -> BriefPlan:
    """A plan of one section, the request itself, for when planning fails."""
    title = " ".join(request.split())[:120]
    return BriefPlan(title=title, sections=[SectionPlan(heading="Findings", question=request)])


def make_plan(llm: LLMClient, request: str) -> tuple[BriefPlan, bool]:
    """The plan for `request` and whether the planner wrote it (False: the fallback)."""
    response = llm.complete(
        plan_messages(request),
        role=PLAN_ROLE,
        temperature=0.0,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    try:
        return parse_plan(response.text), True
    except ValueError:
        return fallback_plan(request), False


# ---------------------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------------------


class Answered(Protocol):
    """What the doc agent and the hybrid return: an answer, with more besides."""

    @property
    def answer(self) -> Answer: ...


class Answerer(Protocol):
    def answer(self, question: str) -> Answered: ...


@dataclass(frozen=True, slots=True)
class Section:
    """One section: its plan, its answer (cut to what its sources support), and the rest."""

    plan: SectionPlan
    answer: Answer
    checked: bool = False
    supported: bool | None = None  # whether every sentence passed, before any cut
    dropped: list[str] = field(default_factory=list)  # sentences the check cut
    error: str | None = None

    @property
    def answered(self) -> bool:
        return self.answer.answerable and bool(self.answer.text.strip())


_CITATION = re.compile(r"\[(\d+)\]")


def renumber(text: str, numbers: dict[int, int]) -> str:
    """`text` with each citation [n] given its number in `numbers`; others are left out."""

    def swap(match: re.Match[str]) -> str:
        number = numbers.get(int(match.group(1)))
        return f"[{number}]" if number is not None else ""

    return re.sub(r"\s+([.,;])", r"\1", _CITATION.sub(swap, text)).strip()


def merge_sources(sections: Sequence[Section]) -> tuple[list[Source], list[dict[int, int]]]:
    """The cited sources of all sections, numbered once for the brief (the same page cited
    by two sections gets one number), and each section's map from its numbers to them."""
    merged: list[Source] = []
    by_key: dict[tuple[str, int, str], int] = {}
    maps: list[dict[int, int]] = []
    for section in sections:
        numbers: dict[int, int] = {}
        for source in section.answer.cited_sources:
            key = (source.doc_name, source.page, source.text)
            if key not in by_key:
                by_key[key] = len(merged) + 1
                merged.append(replace(source, number=len(merged) + 1))
            numbers[source.number] = by_key[key]
        maps.append(numbers)
    return merged, maps


def edit_messages(
    request: str, title: str, headings: Sequence[str], texts: Sequence[str]
) -> list[Message]:
    body = "\n\n".join(
        f"## {heading}\n{text}" for heading, text in zip(headings, texts, strict=True)
    )
    return [system(EDIT_PROMPT), user(f"Request: {request}\n\nBrief: {title}\n\n{body}")]


@dataclass(frozen=True, slots=True)
class Brief:
    """A finished brief; see the module docstring."""

    request: str
    plan: BriefPlan
    planned: bool  # False when the planner's reply held no plan and the fallback was used
    sections: list[Section]  # every planned section, answered or not
    texts: list[str]  # each answered section's text, with the brief's citation numbers
    summary: str
    summary_dropped: list[str]
    sources: list[Source]  # the brief's sources, numbered from 1
    seconds: float = 0.0

    @property
    def answered(self) -> list[Section]:
        return [section for section in self.sections if section.answered]

    @property
    def missing(self) -> list[str]:
        """The headings of the sections the brief couldn't answer."""
        return [section.plan.heading for section in self.sections if not section.answered]

    def markdown(self) -> str:
        parts = [f"# {self.plan.title}"]
        if self.summary:
            parts.append(self.summary)
        parts += [
            f"## {section.plan.heading}\n\n{text}"
            for section, text in zip(self.answered, self.texts, strict=True)
        ]
        if self.missing:
            parts.append(
                "*Not covered, for lack of support in the filings: "
                + "; ".join(self.missing)
                + ".*"
            )
        return "\n\n".join(parts)

    @property
    def citations(self) -> list[dict[str, Any]]:
        cited = {number for text in [self.summary, *self.texts] for number in citations(text)}
        return [
            {
                "number": source.number,
                "label": source.label,
                "doc_name": source.doc_name,
                "page": source.page,
                "text": source.text,
            }
            for source in self.sources
            if source.number in cited
        ]


Emit = Callable[..., None]


def _quiet(*_: Any, **__: Any) -> None:
    return None


class BriefCrew:
    """Plans, writes, checks and edits a brief; see the module docstring.

    `planner` and `editor` call the `strong` role; `checker` the validator's `small` role
    (without it, sections and the summary pass unchecked). `strict=True` lets a
    rate-limited call stop the brief, for batch runs that resume later.
    """

    def __init__(
        self,
        doc: Answerer,
        hybrid: Answerer,
        planner: LLMClient,
        editor: LLMClient,
        checker: LLMClient | None = None,
        *,
        workers: int = 4,
        strict: bool = False,
    ) -> None:
        self.specialists: dict[str, Answerer] = {"doc": doc, "hybrid": hybrid}
        self.planner = planner
        self.editor = editor
        self.checker = checker
        self.workers = workers
        self.strict = strict
        self._one_at_a_time = {"hybrid": threading.Lock()}

    def run(self, request: str, emit: Emit = _quiet) -> Brief:
        started = time.perf_counter()
        plan, planned = make_plan(self.planner, request)
        emit(
            "plan",
            planned=planned,
            title=plan.title,
            modules=plan.modules,
            sections=[{"heading": s.heading, "route": s.route} for s in plan.sections],
        )
        with ThreadPoolExecutor(max_workers=max(1, min(self.workers, len(plan.sections)))) as pool:
            sections = list(pool.map(self.write_section, plan.sections))
        for number, section in enumerate(sections, start=1):
            emit(
                "section",
                number=number,
                heading=section.plan.heading,
                route=section.plan.route,
                answered=section.answered,
                supported=section.supported,
                cut=len(section.dropped),
                error=section.error,
            )
        answered = [section for section in sections if section.answered]
        sources, maps = merge_sources(answered)
        texts = [
            renumber(s.answer.text, numbers) for s, numbers in zip(answered, maps, strict=True)
        ]
        summary, dropped = self._summary(request, plan, answered, texts, sources)
        emit("edit", summary=bool(summary), cut=len(dropped), sources=len(sources))
        return Brief(
            request=request,
            plan=plan,
            planned=planned,
            sections=sections,
            texts=texts,
            summary=summary,
            summary_dropped=dropped,
            sources=sources,
            seconds=round(time.perf_counter() - started, 3),
        )

    def write_section(self, plan: SectionPlan) -> Section:
        """One section: its specialist's answer to its question, checked and cut."""
        specialist = self.specialists[plan.route]
        lock = self._one_at_a_time.get(plan.route)
        try:
            if lock is not None:
                with lock:
                    answer = specialist.answer(plan.question).answer
            else:
                answer = specialist.answer(plan.question).answer
        except LLMError as exc:
            if self.strict and exc.rate_limited:
                raise
            empty = Answer(plan.question, False, "", "", [], [], error=str(exc)[:300])
            return Section(plan, empty, error=str(exc)[:300])
        return self._check(plan, answer)

    def _check(self, plan: SectionPlan, answer: Answer) -> Section:
        if self.checker is None or not answer.answerable or not answer.text.strip():
            return Section(plan, answer)
        try:
            verdict = check_answer(self.checker, answer)
        except LLMError as exc:
            if self.strict and exc.rate_limited:
                raise
            return Section(plan, answer, error=f"unchecked: {str(exc)[:200]}")
        if passes(verdict):
            return Section(plan, answer, checked=True, supported=True)
        kept, dropped = trim(answer, verdict)
        return Section(plan, kept, checked=True, supported=False, dropped=dropped)

    def _summary(
        self,
        request: str,
        plan: BriefPlan,
        answered: Sequence[Section],
        texts: Sequence[str],
        sources: Sequence[Source],
    ) -> tuple[str, list[str]]:
        """The checked summary and the sentences the check cut from it."""
        if not answered:
            return "", []
        headings = [section.plan.heading for section in answered]
        try:
            response = self.editor.complete(
                edit_messages(request, plan.title, headings, texts),
                role=EDIT_ROLE,
                temperature=0.0,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            reply = json_object(response.text)
        except LLMError as exc:
            if self.strict and exc.rate_limited:
                raise
            return "", []
        except ValueError:
            return "", []
        text = str(reply.get("summary", "")).strip() if isinstance(reply, dict) else ""
        numbers = {source.number for source in sources}
        text = renumber(text, {number: number for number in numbers})
        if not text or self.checker is None:
            return text, []
        draft = Answer(request, True, text, "", list(sources), citations(text))
        try:
            verdict = check_answer(self.checker, draft)
        except LLMError as exc:
            if self.strict and exc.rate_limited:
                raise
            return text, []
        if passes(verdict):
            return text, []
        kept, dropped = trim(draft, verdict)
        return (kept.text if kept.answerable else ""), dropped
