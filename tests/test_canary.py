"""The daily canary: its questions in turn, one question asked, a day's summary (ADR-0036)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx

from copilot.eval.canary import FIRST_DAY, ask, doc_questions, failed, summary, todays
from copilot.eval.routing import RoutingQuery, load_queries


def stream(*events: tuple[str, dict[str, object]]) -> str:
    return "".join(f"event: {kind}\ndata: {json.dumps(data)}\n\n" for kind, data in events)


ANSWERED = stream(
    ("meta", {"request_id": "r1", "thread_id": "t1"}),
    ("event", {"event": "route", "route": "doc"}),
    ("response", {"answered": True, "route": "doc", "arm": "fast", "cached": False}),
    (
        "event",
        {
            "event": "reward",
            "arm": "fast",
            "assignment": "policy",
            "judged": True,
            "faithful": True,
        },
    ),
    ("done", {}),
)
QUESTION = RoutingQuery(
    id="r001",
    query="What risks does Netflix name?",
    route="doc",
    seed="s01",
    origin="seed",
    split="dev",
)


def http(text: str, status: int = 200, seen: list[httpx.Request] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, text=text, headers={"content-type": "text/event-stream"})

    return httpx.Client(base_url="http://api", transport=httpx.MockTransport(handler))


def test_the_canary_asks_the_routing_sets_thirty_dev_doc_questions_in_turn() -> None:
    questions = doc_questions(load_queries("dev"))

    assert len(questions) == 30
    assert {question.route for question in questions} == {"doc"}
    first, second, fourth = (todays(questions, FIRST_DAY + timedelta(days=n)) for n in (0, 1, 3))
    assert [q.id for q in first] == [q.id for q in questions[:10]]
    assert [q.id for q in second] == [q.id for q in questions[10:20]]
    assert [q.id for q in fourth] == [q.id for q in questions[:10]]  # every three days, again
    assert todays([], date(2026, 11, 20)) == []


def test_a_question_is_asked_in_a_new_conversation_as_the_canary() -> None:
    seen: list[httpx.Request] = []

    row = ask(http(ANSWERED, seen=seen), QUESTION)

    assert row["ok"] is True
    assert (row["route"], row["arm"], row["assignment"]) == ("doc", "fast", "policy")
    assert (row["answered"], row["judged"], row["faithful"]) == (True, True, True)
    (request,) = seen
    body = json.loads(request.content)
    assert body["question"] == QUESTION.query
    assert len(body["thread_id"]) == 12  # never from the answer cache
    assert (request.headers["x-canary"], request.headers["x-visitor-id"]) == ("1", "canary")


def test_failures_fail_the_day_but_a_busy_api_doesnt() -> None:
    refused = ask(http("", status=503), QUESTION)
    broken = ask(http(stream(("error", {"error": "The copilot failed."}), ("done", {}))), QUESTION)
    busy = ask(
        http(stream(("error", {"error": "The copilot is busy with another question."}))), QUESTION
    )
    silent = ask(http(stream(("done", {}))), QUESTION)

    assert (refused["error"], broken["error"], busy["error"], silent["error"]) == (
        "HTTP 503",
        "error event",
        "busy",
        "no answer",
    )
    assert failed([refused, broken, busy, silent]) == [refused, broken, silent]


def test_a_days_summary_counts_answers_arms_and_verdicts() -> None:
    good = ask(http(ANSWERED), QUESTION)
    busy = {"id": "r002", "ok": False, "error": "busy", "seconds": 120.0}

    found = summary([good, good, busy])

    assert (found["questions"], found["ok"], found["failed"], found["busy"]) == (3, 2, 0, 1)
    assert (found["judged"], found["faithful"], found["answered"]) == (2, 2, 2)
    assert found["arms"] == {"fast": 2}
    assert found["groups"] == {"policy": 2}
