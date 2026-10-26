"""The copilot's graph: each route's path, one shape for answers, turns, traces and quotas."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from copilot.agents.build import postgres_checkpointer
from copilot.agents.graph import NODES, Components, to_draft
from copilot.agents.memory import recall
from copilot.agents.router import Route, RouteDecision
from copilot.agents.runner import Copilot, TraceWriter
from copilot.answer.agent import AgentAnswer, Retrieval
from copilot.answer.context import Source
from copilot.answer.generate import Answer
from copilot.answer.hybrid import DATABASE, DATABASE_LABEL, HybridAnswer
from copilot.config import Settings
from copilot.llm import FakeLLM, LLMClient, LLMError
from copilot.llm.pacing import PacedLLM
from copilot.retrieval.query import CompanyMatcher
from copilot.sql.tool import DataAnswer

MATCHER = CompanyMatcher(["Netflix", "3M"], {"Netflix": "NFLX", "3M": "MMM"})
PAGE = Source(
    number=1,
    doc_name="NETFLIX_2022_10K",
    page=12,
    label="Netflix, Form 10-K for fiscal 2022, PDF page 13",
    text="The market for entertainment is intensely competitive.",
    tokens=9,
)
QUERY = Source(
    number=1, doc_name=DATABASE, page=0, label=DATABASE_LABEL, text="revenue | 2022", tokens=4
)
SQL = "SELECT fiscal_year, value FROM annual_values WHERE metric = 'revenue'"


class FixedRouter:
    """Routes the questions it is asked, in order, to the routes it was given."""

    def __init__(self, routes: Sequence[Route]) -> None:
        self._routes = list(routes)
        self.questions: list[str] = []

    def route(self, question: str) -> RouteDecision:
        self.questions.append(question)
        return RouteDecision(route=self._routes.pop(0), router="fixed", reason="test")


def answer(text: str, sources: Sequence[Source] = (PAGE,), *, answerable: bool = True) -> Answer:
    return Answer(
        question="q",
        answerable=answerable,
        text=text,
        missing="" if answerable else "the risk factors",
        sources=list(sources),
        cited=[source.number for source in sources] if answerable else [],
    )


def data_answer(status: str = "ok", *, rate_limited: bool = False) -> DataAnswer:
    return DataAnswer.model_validate(
        {
            "question": "q",
            "status": status,
            "answer": "Netflix's revenue was $31.6 billion in 2022.",
            "sql": SQL if status == "ok" else None,
            "columns": ["fiscal_year", "value"],
            "rows": [[2022, 31_615_550_000]] if status == "ok" else [],
            "rate_limited": rate_limited,
        }
    )


class FakeDoc:
    def __init__(self, reply: Answer | LLMError) -> None:
        self.reply = reply
        self.questions: list[str] = []

    def answer(self, question: str) -> AgentAnswer:
        self.questions.append(question)
        if isinstance(self.reply, LLMError):
            raise self.reply
        return AgentAnswer(self.reply, Retrieval(["NETFLIX_2022_10K"], [], []))


class FakeData:
    def __init__(self, reply: DataAnswer) -> None:
        self.reply = reply

    def ask(self, question: str, *, analyze: bool = True, hints: Sequence[str] = ()) -> DataAnswer:
        return self.reply.model_copy(update={"question": question})


class FakeHybrid:
    def answer(self, question: str) -> HybridAnswer:
        text = "Revenue rose to $31.6 billion [1] as membership grew [2]."
        page = Source(2, PAGE.doc_name, PAGE.page, PAGE.label, PAGE.text, PAGE.tokens)
        return HybridAnswer(
            answer(text, [QUERY, page]), data_answer(), Retrieval(["NETFLIX_2022_10K"], [], [])
        )


def parts(
    routes: Sequence[Route],
    *,
    doc: FakeDoc | None = None,
    data: FakeData | None = None,
    chat: LLMClient | None = None,
    meters: Sequence[PacedLLM] = (),
    strict: bool = False,
    checker: LLMClient | None = None,
    writer: LLMClient | None = None,
    rewriter: LLMClient | None = None,
    notes: LLMClient | None = None,
    store: BaseStore | None = None,
) -> Components:
    return Components(
        router=FixedRouter(routes),
        doc=doc or FakeDoc(answer("Netflix names intense competition as a risk [1].")),
        data=data or FakeData(data_answer()),
        hybrid=FakeHybrid(),
        matcher=MATCHER,
        chat=chat or FakeLLM(["Hello! Ask me about a company's filings."]),
        companies=["Netflix", "3M"],
        meters=meters,
        strict=strict,
        checker=checker,
        writer=writer,
        rewriter=rewriter,
        notes=notes,
        store=store,
    )


def copilot(
    routes: Sequence[Route],
    *,
    doc: FakeDoc | None = None,
    data: FakeData | None = None,
    chat: LLMClient | None = None,
    meters: Sequence[PacedLLM] = (),
    strict: bool = False,
    trace: TraceWriter | None = None,
    checker: LLMClient | None = None,
    writer: LLMClient | None = None,
) -> Copilot:
    components = parts(
        routes,
        doc=doc,
        data=data,
        chat=chat,
        meters=meters,
        strict=strict,
        checker=checker,
        writer=writer,
    )
    return Copilot(components, trace=trace)


def nodes_run(events: Sequence[dict[str, Any]], kind: str) -> list[str]:
    return [event["node"] for event in events if event["type"] == kind]


@pytest.mark.parametrize(
    ("route", "path"),
    [
        ("doc", ["doc"]),
        ("data", ["data"]),
        ("hybrid", ["hybrid"]),
        ("brief", ["brief"]),
        ("smalltalk", ["smalltalk"]),
        ("decline", ["decline"]),
    ],
)
def test_each_route_runs_its_own_path_through_every_shared_node(
    route: Route, path: list[str]
) -> None:
    events = list(copilot([route]).stream("What risks does Netflix name?", thread_id="t"))

    expected = [
        "rewrite",
        "understand",
        "route",
        *path,
        "synthesise",
        "validate",
        "respond",
        "remember",
    ]
    assert nodes_run(events, "start") == expected
    assert nodes_run(events, "end") == expected
    assert all(event["error"] is None for event in events if event["type"] == "end")
    assert events[-1]["type"] == "response"
    assert events[-1]["route"] == route
    assert set(expected) <= set(NODES)


def test_doc_answers_cite_pages_without_their_text() -> None:
    response = copilot(["doc"]).ask("What risks does Netflix name?", thread_id="t")

    assert response["answered"] is True
    assert response["text"] == "Netflix names intense competition as a risk [1]."
    assert response["citations"] == [
        {"number": 1, "label": PAGE.label, "doc_name": PAGE.doc_name, "page": PAGE.page}
    ]
    assert response["sql"] is None


def test_data_answers_cite_the_query() -> None:
    response = copilot(["data"]).ask("What was Netflix's revenue in 2022?", thread_id="t")

    assert response["answered"] is True
    assert response["sql"] == SQL
    assert response["citations"][0]["doc_name"] == DATABASE
    assert response["citations"][0]["label"] == DATABASE_LABEL


def test_hybrid_answers_cite_the_query_and_the_pages() -> None:
    response = copilot(["hybrid"]).ask("How did Netflix's revenue move, and why?", thread_id="t")

    assert [citation["doc_name"] for citation in response["citations"]] == [
        DATABASE,
        PAGE.doc_name,
    ]
    assert response["sql"] == SQL


def test_a_refusal_says_what_is_missing() -> None:
    doc = FakeDoc(answer("", answerable=False))

    response = copilot(["doc"], doc=doc).ask("What risks does Netflix name?", thread_id="t")

    assert response["answered"] is False
    assert "Missing: the risk factors" in response["text"]
    assert response["citations"] == []


def test_small_talk_uses_the_small_role_and_knows_the_companies() -> None:
    chat = FakeLLM(["Hello! Ask me about a company's filings."])

    response = copilot(["smalltalk"], chat=chat).ask("Hi there!", thread_id="t")

    assert response["text"] == "Hello! Ask me about a company's filings."
    assert chat.calls[0].role == "small"
    assert "Netflix, 3M" in chat.calls[0].messages[0]["content"]


def test_decline_and_brief_reply_without_a_model_call() -> None:
    chat = FakeLLM([])
    pilot = copilot(["decline", "brief"], chat=chat)

    declined = pilot.ask("Should I buy Netflix stock?", thread_id="t")
    briefed = pilot.ask("Write a memo on Netflix.", thread_id="t")

    assert declined["answered"] is False
    assert "investment advice" in declined["text"]
    assert "briefs aren't available yet" in briefed["text"]
    assert chat.calls == []


def test_a_new_turn_starts_clean_and_the_history_grows() -> None:
    pilot = copilot(["doc", "smalltalk"])

    first = pilot.ask("What risks does Netflix name?", thread_id="t")
    second = pilot.ask("Thanks!", thread_id="t")

    assert first["citations"]
    assert second["route"] == "smalltalk"
    assert second["citations"] == []
    assert [turn["route"] for turn in pilot.history("t")] == ["doc", "smalltalk"]
    assert pilot.history("another thread") == []


def test_events_report_the_cues_and_the_route() -> None:
    events = list(copilot(["doc"]).stream("What did Netflix report in 2022?", thread_id="t"))

    custom = {event["event"]: event for event in events if event["type"] == "event"}
    assert custom["cues"]["companies"] == ["Netflix"]
    assert custom["cues"]["years"] == [2022]
    assert custom["route"]["route"] == "doc"
    assert custom["route"]["router"] == "fixed"


def test_the_trace_file_holds_every_event_with_the_run_and_turn(tmp_path: Path) -> None:
    trace = TraceWriter(tmp_path / "traces" / "t.jsonl")
    pilot = copilot(["doc", "decline"], trace=trace)

    pilot.ask("What risks does Netflix name?", thread_id="t")
    pilot.ask("Should I buy it?", thread_id="t")

    lines = [json.loads(line) for line in trace.path.read_text(encoding="utf-8").splitlines()]
    assert {line["turn"] for line in lines} == {1, 2}
    assert len({line["run"] for line in lines}) == 2
    first = [line for line in lines if line["turn"] == 1]
    assert nodes_run(first, "start") == nodes_run(first, "end")
    assert all(line["ms"] >= 0 for line in first if line["type"] == "end")
    assert first[-1]["type"] == "response"


def test_usage_events_report_each_node_s_tokens() -> None:
    meter = PacedLLM(FakeLLM(["Hello there!"]), pause_s=0.0)

    events = list(copilot(["smalltalk"], chat=meter, meters=[meter]).stream("Hi", thread_id="t"))

    used = [event for event in events if event["type"] == "event" and event["event"] == "usage"]
    assert [event["node"] for event in used] == ["smalltalk"]
    assert used[0]["tokens_by_model"] == {"fake/small": [meter.prompt_tokens, 2]}


def test_a_spent_quota_asks_the_user_to_try_later() -> None:
    doc = FakeDoc(LLMError("rate limited", rate_limited=True))

    response = copilot(["doc"], doc=doc).ask("What risks does Netflix name?", thread_id="t")

    assert response["answered"] is False
    assert "try again later" in response["text"]


def test_a_strict_run_stops_on_a_spent_quota_and_traces_the_error(tmp_path: Path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl")
    pilot = copilot(
        ["data"], data=FakeData(data_answer("error", rate_limited=True)), strict=True, trace=trace
    )

    with pytest.raises(LLMError):
        pilot.ask("What was Netflix's revenue?", thread_id="t")

    lines = [json.loads(line) for line in trace.path.read_text(encoding="utf-8").splitlines()]
    assert lines[-1]["type"] == "error"
    assert [line["error"] is not None for line in lines if line["type"] == "end"][-1]


def test_to_draft_handles_every_kind_of_result() -> None:
    assert to_draft({})["kind"] == ""
    assert to_draft({"kind": "decline", "text": "No.", "answered": False})["text"] == "No."
    unanswerable = to_draft({"kind": "data", "data": data_answer("unanswerable").model_dump()})
    assert unanswerable["answered"] is False
    assert unanswerable["citations"] == []
    assert unanswerable["missing"] == unanswerable["text"]


@pytest.mark.integration
def test_a_postgres_conversation_outlives_its_copilot() -> None:
    """Needs the Compose Postgres (`poe services-up`)."""
    thread = f"test-{uuid.uuid4().hex[:8]}"
    with postgres_checkpointer(Settings(_env_file=None)) as saver:
        Copilot(parts(["doc"]), saver).ask("What risks does Netflix name?", thread_id=thread)
        later = Copilot(parts(["smalltalk"]), saver)
        later.ask("Thanks!", thread_id=thread)

        assert [turn["route"] for turn in later.history(thread)] == ["doc", "smalltalk"]


PASS = json.dumps({"sentences": [{"n": 1, "supported": True, "supporting": [1]}]})
FAIL = json.dumps({"sentences": [{"n": 1, "supported": False, "supporting": []}]})
FIXED = "The market for entertainment is intensely competitive, Netflix says [1]."


def revision(text: str = FIXED) -> str:
    return json.dumps({"answerable": True, "answer": text, "calculations": [], "missing": ""})


def test_without_a_checker_answers_pass_unchecked() -> None:
    response = copilot(["doc"]).ask("What risks does Netflix name?", thread_id="t")

    assert response["validation"] == {"checked": False}


def test_a_faithful_answer_is_checked_once() -> None:
    checker, writer = FakeLLM([PASS]), FakeLLM([])
    pilot = copilot(["doc"], checker=checker, writer=writer)

    events = list(pilot.stream("What risks does Netflix name?", thread_id="t"))

    assert "revise" not in nodes_run(events, "start")
    assert events[-1]["validation"] == {"checked": True, "faithful": True, "revisions": 0}
    assert checker.calls[0].role == "small"
    assert writer.calls == []


def test_a_failing_answer_is_revised_and_checked_again() -> None:
    checker, writer = FakeLLM([FAIL, PASS]), FakeLLM([revision()])
    pilot = copilot(["doc"], checker=checker, writer=writer)

    events = list(pilot.stream("What risks does Netflix name?", thread_id="t"))

    path = nodes_run(events, "start")
    assert path[-5:] == ["validate", "revise", "validate", "respond", "remember"]
    response = events[-1]
    assert response["text"] == FIXED
    assert response["validation"] == {"checked": True, "faithful": True, "revisions": 1}
    assert writer.calls[0].role == "strong"
    assert "intense competition as a risk [1]." in writer.calls[0].messages[-1]["content"]


def test_two_failed_revisions_leave_only_what_was_verified() -> None:
    checker = FakeLLM([FAIL, FAIL, FAIL])
    writer = FakeLLM([revision(), revision()])
    pilot = copilot(["doc"], checker=checker, writer=writer)

    events = list(pilot.stream("What risks does Netflix name?", thread_id="t"))

    assert nodes_run(events, "start").count("revise") == 2
    response = events[-1]
    assert response["answered"] is False
    assert response["validation"]["revisions"] == 2
    assert response["validation"]["unverified"] == [FIXED]
    assert "unverified" in response["text"]


def test_data_answers_and_refusals_are_not_checked() -> None:
    checker = FakeLLM([])
    pilot = copilot(["data", "doc"], checker=checker, writer=FakeLLM([]))
    refusing = FakeDoc(answer("", answerable=False))

    data = pilot.ask("What was Netflix's revenue in 2022?", thread_id="t")
    refused = copilot(["doc"], doc=refusing, checker=checker, writer=FakeLLM([])).ask(
        "What risks does Netflix name?", thread_id="t"
    )

    assert data["validation"] == {"checked": False}
    assert refused["validation"] == {"checked": False}
    assert checker.calls == []


def test_a_revision_that_declines_is_reported() -> None:
    checker = FakeLLM([FAIL])
    refusal = {"answerable": False, "answer": "", "calculations": [], "missing": "the risks"}
    pilot = copilot(["doc"], checker=checker, writer=FakeLLM([json.dumps(refusal)]))

    response = pilot.ask("What risks does Netflix name?", thread_id="t")

    assert response["answered"] is False
    assert response["validation"] == {"checked": True, "refused": True, "revisions": 1}
    assert len(checker.calls) == 1


def test_a_follow_up_reaches_the_router_as_a_standalone_question() -> None:
    rewriter = FakeLLM([json.dumps({"standalone": "What was Netflix's revenue in 2021?"})])
    components = parts(["data", "data"], rewriter=rewriter)
    pilot = Copilot(components)

    pilot.ask("What was Netflix's revenue in 2022?", thread_id="t")
    second = pilot.ask("And in 2021?", thread_id="t")

    router = components.router
    assert isinstance(router, FixedRouter)
    assert router.questions == [
        "What was Netflix's revenue in 2022?",
        "What was Netflix's revenue in 2021?",
    ]
    assert second["question"] == "And in 2021?"
    assert second["standalone"] == "What was Netflix's revenue in 2021?"
    assert len(rewriter.calls) == 1  # the first question needed no rewrite
    assert "Q1: What was Netflix's revenue in 2022?" in rewriter.calls[0].messages[1]["content"]


def test_notes_carry_over_to_a_new_conversation() -> None:
    store = InMemoryStore()
    notes = FakeLLM(
        [
            json.dumps({"facts": ["Follows Netflix."]}),
            json.dumps({"operations": [{"action": "add", "text": "Follows Netflix."}]}),
            json.dumps({"facts": []}),
        ]
    )
    rewriter = FakeLLM([json.dumps({"standalone": "How did Netflix's revenue change last year?"})])
    components = parts(["doc", "doc"], rewriter=rewriter, notes=notes, store=store)
    pilot = Copilot(components)

    pilot.ask("I follow Netflix. What risks does it name?", thread_id="first", user_id="u1")
    pilot.ask("How did their revenue change last year?", thread_id="second", user_id="u1")

    assert [note.text for note in recall(store, "u1")] == ["Follows Netflix."]
    assert "- Follows Netflix." in rewriter.calls[0].messages[1]["content"]
    assert recall(store, "default") == []


def test_anonymous_users_keep_and_read_no_notes() -> None:
    store = InMemoryStore()
    store.put(("notes", "anon-t"), "n1", {"text": "Follows Netflix."})
    notes, rewriter = FakeLLM([]), FakeLLM([])  # any call to either would fail the test
    components = parts(["doc"], rewriter=rewriter, notes=notes, store=store)

    events = list(
        Copilot(components).stream(
            "I follow Netflix. What risks does it name?", thread_id="t", user_id="anon-t"
        )
    )

    remembered = [e for e in events if e["type"] == "event" and e.get("node") == "remember"]
    assert (remembered[0]["event"], remembered[0]["reason"]) == ("skipped", "anonymous")
    assert notes.calls == []
    assert rewriter.calls == []


def test_without_a_store_no_notes_are_kept() -> None:
    events = list(copilot(["doc"]).stream("What risks does Netflix name?", thread_id="t"))

    remembered = [e for e in events if e["type"] == "event" and e.get("node") == "remember"]
    assert remembered[0]["event"] == "skipped"
