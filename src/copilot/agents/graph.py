"""The copilot as a LangGraph state graph (step 5.1, ADR-0018).

Each question runs through the same nodes:

    rewrite -> understand -> route -> doc | data | hybrid | brief | smalltalk | decline
            -> synthesise -> validate (-> revise -> validate, at most twice) -> respond

- **rewrite** makes a follow-up standalone (a pass-through until step 5.5 adds follow-up
  rewriting) and clears what the previous turn left in the state.
- **understand** reads the companies, periods and forms the question names.
- **route** asks the router (ADR-0017) and branches on its route.
- The specialists answer: the doc agent, the data agent, the hybrid of the two, a brief
  (Phase 7; a short note until then), a reply to small talk, or a polite decline.
- **synthesise** puts every specialist's result into one shape, the draft.
- **validate** checks a cited answer's sentences against their sources (step 5.3,
  `copilot.agents.validator`). An answer that fails goes to **revise** and back, at most
  twice; after that, only its verified sentences are kept.
- **respond** writes the reply and adds the turn to the conversation's history.

The state holds plain JSON values only, so any checkpointer can store it: in memory for
tests, Postgres for conversations that outlive the process. Nodes report what they did as
custom stream events (`emit`), and `copilot.agents.runner` turns the stream into JSON-line
traces, one start and one end per node.
"""

from __future__ import annotations

import operator
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Annotated, Any, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from copilot.agents.router import ROUTES, Route, RouteDecision
from copilot.agents.validator import MAX_REVISIONS, check_answer, to_answer, trim, verdict_record
from copilot.agents.validator import revise as revise_answer
from copilot.answer.agent import AgentAnswer
from copilot.answer.generate import SYSTEM_PROMPT as DOC_PROMPT
from copilot.answer.generate import Answer
from copilot.answer.hybrid import DATABASE, DATABASE_LABEL, HybridAnswer
from copilot.answer.hybrid_v2 import SYSTEM_PROMPT as HYBRID_PROMPT
from copilot.eval.faithfulness import SentenceCheck
from copilot.llm import LLMClient, LLMError, system, user
from copilot.llm.gateway import token_cost
from copilot.llm.pacing import PacedLLM
from copilot.retrieval.query import CompanyMatcher, understand
from copilot.sql.tool import DataAnswer

NODES = (
    "rewrite",
    "understand",
    "route",
    *ROUTES,
    "synthesise",
    "validate",
    "revise",
    "respond",
)


# ---------------------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------------------


class Turn(TypedDict):
    """One finished exchange, kept in the conversation's history."""

    question: str
    standalone: str
    route: str
    answer: str


class CopilotState(TypedDict, total=False):
    question: str  # as asked, this turn
    standalone: str  # after follow-up rewriting
    cues: dict[str, Any]  # the companies, periods and forms the question names
    decision: dict[str, Any]  # the router's RouteDecision
    route: str
    result: dict[str, Any]  # the specialist's output
    draft: dict[str, Any]  # every specialist's output in one shape
    response: dict[str, Any]  # what the user gets
    validation: dict[str, Any]  # the latest check of the draft's sentences
    revisions: int  # how many times the draft was written again after a check
    history: Annotated[list[Turn], operator.add]  # earlier turns, oldest first


# Everything a turn writes, cleared when the next turn starts, so a checkpointed
# conversation never carries one turn's route or sources into the next.
PER_TURN: dict[str, Any] = {
    "standalone": "",
    "cues": {},
    "decision": {},
    "route": "",
    "result": {},
    "draft": {},
    "response": {},
    "validation": {},
    "revisions": 0,
}


# ---------------------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------------------


class Router(Protocol):
    def route(self, question: str) -> RouteDecision: ...


class DocAnswerer(Protocol):
    def answer(self, question: str) -> AgentAnswer: ...


class DataAsker(Protocol):
    def ask(
        self, question: str, *, analyze: bool = True, hints: Sequence[str] = ()
    ) -> DataAnswer: ...


class HybridAnswerer(Protocol):
    def answer(self, question: str) -> HybridAnswer: ...


@dataclass
class Components:
    """What the nodes call.

    `chat` writes the small-talk replies, on the `small` role. `meters` are the paced
    clients behind the components, whose tokens each node reports as it uses them.
    `strict=True` lets a rate-limited model call stop the run, for batch evaluations that
    resume later; otherwise the reply asks the user to try again. `checker` checks cited
    answers on the `small` role and `writer` revises them on the `strong` role; without
    both, answers pass unchecked.
    """

    router: Router
    doc: DocAnswerer
    data: DataAsker
    hybrid: HybridAnswerer
    matcher: CompanyMatcher
    chat: LLMClient
    companies: Sequence[str] = ()
    meters: Sequence[PacedLLM] = ()
    strict: bool = False
    checker: LLMClient | None = None
    writer: LLMClient | None = None


BRIEF_REPLY = (
    "Written briefs aren't available yet. Ask about one part at a time, such as a "
    "company's revenue trend, what drove it, or the risks it reports, and I'll answer "
    "with sources."
)
DECLINE_REPLY = (
    "I can't help with that. I answer questions about what US public companies report in "
    "their 10-K and 10-Q filings, and the figures in them, with sources. I don't give "
    "investment advice, predict prices or help with tasks outside the filings."
)
QUOTA_REPLY = "The language model's free quota is used up for now. Please try again later."
SMALLTALK_PROMPT = (
    "You are the research assistant of a copilot for public-company filings. It answers "
    "questions about the 10-K and 10-Q filings, and the figures reported in them, of these "
    "companies: {companies}. Every answer cites its sources: filing pages, or the query "
    "behind a figure. It doesn't give investment advice or predict prices. Reply to the "
    "user's message briefly and warmly, in one to three sentences, and suggest a kind of "
    "question it can answer when that helps."
)


# ---------------------------------------------------------------------------------------
# Events and usage
# ---------------------------------------------------------------------------------------


def emit(node: str, event: str, **data: Any) -> None:
    """Report what a node did as a custom stream event; nothing happens outside a stream."""
    get_stream_writer()({"node": node, "event": event, **data})


def usage(meters: Iterable[PacedLLM]) -> dict[str, tuple[int, int]]:
    """Prompt and completion tokens by model across the clients, so far."""
    total: dict[str, tuple[int, int]] = {}
    for meter in meters:
        for model, (prompt, completion) in meter.tokens_by_model.items():
            old_prompt, old_completion = total.get(model, (0, 0))
            total[model] = (old_prompt + prompt, old_completion + completion)
    return total


class Node(Protocol):
    """A node: the state in, the keys it updates out."""

    def __call__(self, state: CopilotState) -> dict[str, Any]: ...


def metered(name: str, node: Node, meters: Sequence[PacedLLM]) -> Node:
    """`node`, followed by a `usage` event with the model tokens and cost it spent."""

    def run(state: CopilotState) -> dict[str, Any]:
        before = usage(meters)
        started = time.perf_counter()
        update = node(state)
        spent: dict[str, list[int]] = {}
        for model, (prompt, completion) in usage(meters).items():
            old_prompt, old_completion = before.get(model, (0, 0))
            if (prompt, completion) != (old_prompt, old_completion):
                spent[model] = [prompt - old_prompt, completion - old_completion]
        if spent:
            costs = [token_cost(model, p, c) for model, (p, c) in spent.items()]
            known = [cost for cost in costs if cost is not None]
            emit(
                name,
                "usage",
                tokens_by_model=spent,
                cost_usd=round(sum(known), 7) if len(known) == len(costs) else None,
                seconds=round(time.perf_counter() - started, 3),
            )
        return update

    return run


# ---------------------------------------------------------------------------------------
# Results as plain JSON
# ---------------------------------------------------------------------------------------


def answer_record(answer: Answer) -> dict[str, Any]:
    """An answer as the state holds it, with every source's text, for the validator."""
    return {
        "answerable": answer.answerable,
        "text": answer.text,
        "missing": answer.missing,
        "error": answer.error,
        "cited": list(answer.cited),
        "sources": [asdict(source) for source in answer.sources],
        "citations": [
            {
                "number": source.number,
                "label": source.label,
                "doc_name": source.doc_name,
                "page": source.page,
                "text": source.text,
            }
            for source in answer.cited_sources
        ],
        "calculations": [asdict(calculation) for calculation in answer.calculations],
    }


def data_record(answer: DataAnswer) -> dict[str, Any]:
    return answer.model_dump(mode="json", exclude={"question"})


def to_draft(result: dict[str, Any]) -> dict[str, Any]:
    """Every specialist's result in one shape: the text, whether it answers, its citations."""
    kind = result.get("kind", "")
    if kind in ("doc", "hybrid") and "answer" in result:
        answer = result["answer"]
        database = any(c["doc_name"] == DATABASE for c in answer["citations"])
        return {
            "kind": kind,
            "text": answer["text"] or _refusal(answer["missing"]),
            "answered": answer["answerable"],
            "missing": answer["missing"],
            "citations": answer["citations"],
            "sql": (result.get("data") or {}).get("sql") if database else None,
        }
    if kind == "data" and "data" in result:
        data = result["data"]
        answered = data["status"] == "ok"
        query = {"number": 1, "label": DATABASE_LABEL, "doc_name": DATABASE, "page": None}
        return {
            "kind": kind,
            "text": data["answer"],
            "answered": answered,
            "missing": "" if answered else data["answer"],
            "citations": [query] if answered and data.get("sql") else [],
            "sql": data.get("sql"),
        }
    return {
        "kind": kind,
        "text": result.get("text", ""),
        "answered": bool(result.get("answered", False)),
        "missing": "",
        "citations": [],
        "sql": None,
    }


def _refusal(missing: str) -> str:
    missing = missing.strip()
    if missing:
        return f"The filings I searched don't contain the answer. Missing: {missing}"
    return "The filings I searched don't contain the answer."


# ---------------------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------------------


def branch(state: CopilotState) -> Route:
    """The node after `route`: the route's own, or the doc agent for anything unknown."""
    route = state.get("route", "")
    for known in ROUTES:
        if route == known:
            return known
    return "doc"


def after_validation(state: CopilotState) -> str:
    """`revise` when the check asked for another draft, else `respond`."""
    return "revise" if state.get("validation", {}).get("next") == "revise" else "respond"


def build_graph(
    parts: Components, checkpointer: Checkpointer = None
) -> CompiledStateGraph[CopilotState, None, CopilotState, CopilotState]:
    """The copilot's graph over `parts`; see the module docstring."""

    def quota(node: str, exc: LLMError) -> dict[str, Any]:
        if parts.strict or not exc.rate_limited:
            raise exc
        emit(node, "quota", error=str(exc)[:200])
        return {"result": {"kind": node, "text": QUOTA_REPLY, "answered": False}}

    def rewrite(state: CopilotState) -> dict[str, Any]:
        question = " ".join(state["question"].split())
        emit("rewrite", "standalone", standalone=question, rewritten=False)
        return {**PER_TURN, "standalone": question}

    def understand_question(state: CopilotState) -> dict[str, Any]:
        cues = understand(state["standalone"], parts.matcher)
        record = {
            "companies": list(cues.companies),
            "years": list(cues.years),
            "quarters": [list(quarter) for quarter in cues.quarters],
            "forms": list(cues.forms),
        }
        emit("understand", "cues", **record)
        return {"cues": record}

    def route(state: CopilotState) -> dict[str, Any]:
        decision = parts.router.route(state["standalone"])
        emit(
            "route",
            "route",
            route=decision.route,
            router=decision.router,
            model=decision.model,
            reason=decision.reason,
            confidence=decision.confidence,
            error=decision.error,
        )
        return {"decision": asdict(decision), "route": decision.route}

    def doc(state: CopilotState) -> dict[str, Any]:
        try:
            agent_answer = parts.doc.answer(state["standalone"])
        except LLMError as exc:
            return quota("doc", exc)
        record = answer_record(agent_answer.answer)
        filings = agent_answer.retrieval.filings
        emit(
            "doc",
            "answer",
            answered=record["answerable"],
            retried=agent_answer.retried,
            cited=len(record["citations"]),
            filings=filings,
        )
        result = {"kind": "doc", "answer": record, "retried": agent_answer.retried}
        return {"result": result | {"filings": filings}}

    def data(state: CopilotState) -> dict[str, Any]:
        answer = parts.data.ask(state["standalone"])
        if answer.rate_limited:
            return quota("data", LLMError(answer.answer, rate_limited=True))
        emit("data", "answer", status=answer.status, sql=answer.sql, rows=len(answer.rows))
        return {"result": {"kind": "data", "data": data_record(answer)}}

    def hybrid(state: CopilotState) -> dict[str, Any]:
        try:
            found = parts.hybrid.answer(state["standalone"])
        except LLMError as exc:
            return quota("hybrid", exc)
        record = answer_record(found.answer)
        data = data_record(found.data) if found.data is not None else None
        emit(
            "hybrid",
            "answer",
            path=found.path,
            figures_question=found.figures_question,
            reasons_question=found.reasons_question,
            answered=record["answerable"],
            retried=found.retried,
            data_status=data["status"] if data else None,
            database_cited=found.database_cited,
            pages_cited=found.pages_cited,
        )
        result = {"kind": "hybrid", "answer": record, "data": data, "path": found.path}
        return {"result": result | {"filings": found.retrieval.filings}}

    def brief(state: CopilotState) -> dict[str, Any]:
        emit("brief", "not yet", note="research briefs arrive in Phase 7")
        return {"result": {"kind": "brief", "text": BRIEF_REPLY, "answered": False}}

    def smalltalk(state: CopilotState) -> dict[str, Any]:
        prompt = SMALLTALK_PROMPT.format(companies=", ".join(parts.companies) or "about 40")
        try:
            response = parts.chat.complete(
                [system(prompt), user(state["standalone"])],
                role="small",
                temperature=0.3,
                max_tokens=512,
            )
        except LLMError as exc:
            return quota("smalltalk", exc)
        return {"result": {"kind": "smalltalk", "text": response.text.strip(), "answered": True}}

    def decline(state: CopilotState) -> dict[str, Any]:
        emit("decline", "declined", reason=state.get("decision", {}).get("reason"))
        return {"result": {"kind": "decline", "text": DECLINE_REPLY, "answered": False}}

    def synthesise(state: CopilotState) -> dict[str, Any]:
        draft = to_draft(state.get("result", {}))
        emit(
            "synthesise",
            "draft",
            kind=draft["kind"],
            answered=draft["answered"],
            citations=len(draft["citations"]),
        )
        return {"draft": draft}

    def validate(state: CopilotState) -> dict[str, Any]:
        result = state.get("result", {})
        record = result.get("answer")
        if parts.checker is None or parts.writer is None:
            emit("validate", "skipped", reason="no checker")
            return {"validation": {"checked": False}}
        if result.get("kind") not in ("doc", "hybrid") or not record or not record["answerable"]:
            emit("validate", "skipped", reason="no cited answer to check")
            return {"validation": {"checked": False}}
        answer = to_answer(record, state["standalone"])
        try:
            verdict = check_answer(parts.checker, answer)
        except LLMError as exc:
            if parts.strict or not exc.rate_limited:
                raise
            emit("validate", "quota", error=str(exc)[:200])
            return {"validation": {"checked": False, "error": "the checker's quota is used up"}}
        revisions = state.get("revisions", 0)
        checked = verdict_record(verdict) | {"checked": True, "revisions": revisions}
        emit(
            "validate",
            "verdict",
            faithful=verdict.faithful,
            sentences=len(verdict.checks),
            supported=verdict.supported_sentences,
            revisions=revisions,
        )
        if verdict.faithful:
            return {"validation": checked}
        if revisions < MAX_REVISIONS:
            return {"validation": checked | {"next": "revise"}}
        trimmed, dropped = trim(answer, verdict)
        emit("validate", "trimmed", kept=verdict.supported_sentences, unverified=len(dropped))
        kept = result | {"answer": answer_record(trimmed)}
        return {
            "result": kept,
            "draft": to_draft(kept),
            "validation": checked | {"unverified": dropped},
        }

    def revise(state: CopilotState) -> dict[str, Any]:
        result = state["result"]
        answer = to_answer(result["answer"], state["standalone"])
        failed = [SentenceCheck(**sentence) for sentence in state["validation"]["failing"]]
        split = result.get("kind") == "hybrid" and result.get("path") == "split"
        prompt = HYBRID_PROMPT if split else DOC_PROMPT
        revisions = state.get("revisions", 0) + 1
        assert parts.writer is not None  # validate sends answers here only with a writer
        try:
            revised = revise_answer(parts.writer, prompt, state["standalone"], answer, failed)
        except LLMError as exc:
            if parts.strict or not exc.rate_limited:
                raise
            emit("revise", "quota", error=str(exc)[:200])
            return {"revisions": MAX_REVISIONS}  # stop revising; the next check trims
        emit("revise", "revised", answered=revised.answerable, revision=revisions)
        rewritten = result | {"answer": answer_record(revised)}
        return {"result": rewritten, "draft": to_draft(rewritten), "revisions": revisions}

    def respond(state: CopilotState) -> dict[str, Any]:
        draft = state.get("draft", {})
        response = {
            "question": state["question"],
            "standalone": state["standalone"],
            "route": state.get("route", ""),
            "text": draft.get("text", ""),
            "answered": draft.get("answered", False),
            "missing": draft.get("missing", ""),
            "citations": [
                {key: value for key, value in citation.items() if key != "text"}
                for citation in draft.get("citations", [])
            ],
            "sql": draft.get("sql"),
            "validation": {
                key: value
                for key, value in state.get("validation", {}).items()
                if key in ("checked", "faithful", "revisions", "unverified")
            },
        }
        turn: Turn = {
            "question": state["question"],
            "standalone": state["standalone"],
            "route": response["route"],
            "answer": response["text"],
        }
        return {"response": response, "history": [turn]}

    nodes: dict[str, Node] = {
        "rewrite": rewrite,
        "understand": understand_question,
        "route": route,
        "doc": doc,
        "data": data,
        "hybrid": hybrid,
        "brief": brief,
        "smalltalk": smalltalk,
        "decline": decline,
        "synthesise": synthesise,
        "validate": validate,
        "revise": revise,
        "respond": respond,
    }
    builder = StateGraph(CopilotState)
    for name, node in nodes.items():
        builder.add_node(name, metered(name, node, parts.meters))
    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "understand")
    builder.add_edge("understand", "route")
    builder.add_conditional_edges("route", branch, {name: name for name in ROUTES})
    for name in ROUTES:
        builder.add_edge(name, "synthesise")
    builder.add_edge("synthesise", "validate")
    builder.add_conditional_edges(
        "validate", after_validation, {"revise": "revise", "respond": "respond"}
    )
    builder.add_edge("revise", "validate")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=checkpointer)
