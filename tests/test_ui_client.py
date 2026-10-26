"""The UI's client: server-sent events read from a stream, refusals, feedback and pages."""

from __future__ import annotations

import json

import httpx

from copilot.ui.client import CopilotClient, Event, parse_sse

STREAM = (
    'event: meta\ndata: {"request_id": "r1", "thread_id": "t1"}\n\n'
    ": ping\n\n"
    'event: start\nid: 1\ndata: {"node": "route"}\n\n'
    "event: response\nid: 2\n"
    'data: {"text": "Capex was $1,577 million [1].",\ndata:  "answered": true}\n\n'
    'event: done\ndata: {"thread_id": "t1"}\n\n'
)


def client(handler: httpx.MockTransport) -> CopilotClient:
    return CopilotClient("http://api", "visitor-0001", transport=handler)


def test_parse_sse_reads_events_and_skips_comments() -> None:
    events = list(parse_sse(STREAM.split("\n")))

    assert [e.kind for e in events] == ["meta", "start", "response", "done"]
    assert events[2].data == {"text": "Capex was $1,577 million [1].", "answered": True}


def test_a_question_streams_its_events_with_the_visitor_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["visitor"] = request.headers["x-visitor-id"]
        return httpx.Response(200, text=STREAM, headers={"content-type": "text/event-stream"})

    events = list(client(httpx.MockTransport(handler)).ask("What was 3M's capex?", "t1"))

    assert events[0] == Event("meta", {"request_id": "r1", "thread_id": "t1"})
    assert seen == {
        "body": {"question": "What was 3M's capex?", "thread_id": "t1"},
        "visitor": "visitor-0001",
    }


def test_refusals_and_outages_become_one_error_event() -> None:
    over = httpx.MockTransport(
        lambda r: httpx.Response(
            429, json={"detail": "Quota used up."}, headers={"Retry-After": "60"}
        )
    )
    bad = httpx.MockTransport(lambda r: httpx.Response(422, json={"detail": []}))

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert list(client(over).ask("q")) == [
        Event("error", {"error": "Quota used up.", "retry_after": "60"})
    ]
    assert "empty or too long" in next(iter(client(bad).ask(""))).data["error"]
    unreachable = next(iter(client(httpx.MockTransport(down)).ask("q")))
    assert "can't be reached" in unreachable.data["error"]


def test_feedback_pages_and_readiness() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/feedback":
            return httpx.Response(201, json={"id": 7})
        if request.url.path == "/v1/sources/3M_2018_10K/59":
            return httpx.Response(200, json={"label": "3M, PDF page 60", "text": "Capex..."})
        if request.url.path == "/readyz":
            return httpx.Response(503, json={"ready": False, "checks": {"qdrant": False}})
        return httpx.Response(404, json={"detail": "No such page."})

    api = client(httpx.MockTransport(handler))

    assert api.feedback("t1", 1, "up", "r1") is True
    assert api.source("3M_2018_10K", 59) == {"label": "3M, PDF page 60", "text": "Capex..."}
    assert api.source("3M_2018_10K", 999) is None
    assert api.ready() == {"ready": False, "checks": {"qdrant": False}}
