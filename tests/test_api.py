"""The API: streamed answers, feedback, cited pages, health checks and request ids."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from copilot.api import app as api
from copilot.api.services import Asker, MemoryFeedback, Services
from copilot.ingest.pdf import Page, write_pages
from copilot.retrieval.query import Filing

QUESTION = "What was 3M's capital expenditure in fiscal 2018?"


class FakeCopilot:
    """Yields what the runner yields for a doc question; can fail mid-run like the graph."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str, str]] = []

    def stream(
        self, question: str, *, thread_id: str, user_id: str = "default"
    ) -> Iterator[dict[str, Any]]:
        self.calls.append((question, thread_id, user_id))
        base = {"thread": thread_id, "turn": 1}
        yield base | {"type": "start", "node": "route"}
        yield base | {"type": "event", "event": "route", "route": "doc"}
        yield base | {"type": "end", "node": "route", "ms": 3.0, "error": None}
        if self.fail is not None:
            yield base | {"type": "error", "error": "RuntimeError: boom"}
            raise self.fail
        yield base | {"type": "response", "text": "Capex was $1,577 million [1].", "answered": True}


class BrokenCopilot:
    """Fails before the graph starts, so no error event comes from the runner."""

    def stream(
        self, question: str, *, thread_id: str, user_id: str = "default"
    ) -> Iterator[dict[str, Any]]:
        raise ConnectionError("the checkpointer's database is down")
        yield {}  # pragma: no cover - makes this a generator


def make_services(
    tmp_path: Path,
    copilot: Asker | None = None,
    checks: Callable[[], dict[str, bool]] | None = None,
) -> Services:
    pages = tmp_path / "pages"
    write_pages(
        [
            Page("3M_2018_10K", 0, "Annual report", None, ()),
            Page("3M_2018_10K", 1, "Purchases of PP&E were $1,577 million.", "Item 7", ()),
        ],
        pages / "3M_2018_10K.jsonl",
    )
    return Services(
        copilot=copilot or FakeCopilot(),
        feedback=MemoryFeedback(),
        pages_dir=pages,
        checks=checks or (lambda: {"qdrant": True, "llm_key": True}),
        filings={"3M_2018_10K": Filing("3M_2018_10K", "3M", "10k", 2018)},
    )


def sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    """A server-sent event stream as (event, data) pairs, keep-alive comments left out."""
    parsed = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        kind, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
        if data is not None:
            parsed.append((kind, data))
    return parsed


def test_health_and_readiness(tmp_path: Path) -> None:
    with TestClient(api.create_app(make_services(tmp_path))) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        ready = client.get("/readyz")
        assert (ready.status_code, ready.json()["ready"]) == (200, True)

    not_ready = make_services(tmp_path / "b", checks=lambda: {"qdrant": False, "llm_key": True})
    with TestClient(api.create_app(not_ready)) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json() == {"ready": False, "checks": {"qdrant": False, "llm_key": True}}


def test_a_question_streams_the_graphs_events(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        response = client.post("/v1/ask", json={"question": f"  {QUESTION} "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse(response.text)
    assert [kind for kind, _ in events] == ["meta", "start", "event", "end", "response", "done"]
    meta = events[0][1]
    assert meta["request_id"] == response.headers["x-request-id"]
    assert len(meta["thread_id"]) == 12
    assert events[4][1]["text"] == "Capex was $1,577 million [1]."
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    assert copilot.calls == [(QUESTION, meta["thread_id"], "default")]


def test_a_follow_up_continues_its_thread_and_keeps_the_request_id(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    body = {"question": "And in 2019?", "thread_id": "t-1", "user_id": "u1"}
    with TestClient(api.create_app(services)) as client:
        given = client.post("/v1/ask", json=body, headers={"X-Request-ID": "abc-123"})
        invalid = client.post("/v1/ask", json=body, headers={"X-Request-ID": "not valid!"})

    assert given.headers["x-request-id"] == "abc-123"
    assert sse(given.text)[0][1] == {"request_id": "abc-123", "thread_id": "t-1"}
    assert invalid.headers["x-request-id"] != "not valid!"
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    assert copilot.calls[0] == ("And in 2019?", "t-1", "u1")


@pytest.mark.parametrize(
    "body",
    [
        {"question": "   "},
        {"question": "x" * 2001},
        {"question": QUESTION, "thread_id": "a/b"},
        {"question": QUESTION, "unknown": 1},
    ],
)
def test_bad_questions_are_refused_before_any_run(tmp_path: Path, body: dict[str, Any]) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        assert client.post("/v1/ask", json=body).status_code == 422
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    assert copilot.calls == []


def test_a_failed_run_ends_with_one_error_then_done(tmp_path: Path) -> None:
    failing = make_services(tmp_path, copilot=FakeCopilot(fail=RuntimeError("boom")))
    with TestClient(api.create_app(failing)) as client:
        events = [kind for kind, _ in sse(client.post("/v1/ask", json={"question": QUESTION}).text)]
    assert events == ["meta", "start", "event", "end", "error", "done"]

    broken = make_services(tmp_path / "b", copilot=BrokenCopilot())
    with TestClient(api.create_app(broken)) as client:
        events = [kind for kind, _ in sse(client.post("/v1/ask", json={"question": QUESTION}).text)]
    assert events == ["meta", "error", "done"]


def test_a_busy_copilot_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    services = make_services(tmp_path)
    monkeypatch.setattr(api, "BUSY_WAIT_S", 0.01)
    services.lock.acquire()
    try:
        with TestClient(api.create_app(services)) as client:
            events = sse(client.post("/v1/ask", json={"question": QUESTION}).text)
    finally:
        services.lock.release()

    assert [kind for kind, _ in events] == ["meta", "error", "done"]
    assert "busy" in events[1][1]["error"]


def test_feedback_is_kept(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    body = {"thread_id": "t-1", "turn": 1, "rating": "up", "comment": " clear answer "}
    with TestClient(api.create_app(services)) as client:
        receipt = client.post("/v1/feedback", json=body)
        refused = client.post("/v1/feedback", json=body | {"rating": "meh"})

    assert (receipt.status_code, receipt.json()) == (201, {"id": 1})
    assert refused.status_code == 422
    feedback = services.feedback
    assert isinstance(feedback, MemoryFeedback)
    kept = feedback.records[0][1]
    assert (kept.thread_id, kept.turn, kept.rating, kept.comment) == (
        "t-1",
        1,
        "up",
        "clear answer",
    )


def test_a_cited_page_is_served_with_its_label(tmp_path: Path) -> None:
    with TestClient(api.create_app(make_services(tmp_path))) as client:
        page = client.get("/v1/sources/3M_2018_10K/1")
        missing_page = client.get("/v1/sources/3M_2018_10K/5")
        missing_doc = client.get("/v1/sources/Nike_2018_10K/1")
        bad_name = client.get("/v1/sources/.hidden/1")

    assert page.json() == {
        "doc_name": "3M_2018_10K",
        "page": 1,
        "label": "3M, Form 10-K for fiscal 2018, PDF page 2",
        "section": "Item 7",
        "text": "Purchases of PP&E were $1,577 million.",
    }
    assert (missing_page.status_code, missing_doc.status_code) == (404, 404)
    assert bad_name.status_code == 422


def test_the_openapi_document_lists_every_endpoint(tmp_path: Path) -> None:
    with TestClient(api.create_app(make_services(tmp_path))) as client:
        paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/healthz",
        "/readyz",
        "/v1/ask",
        "/v1/feedback",
        "/v1/sources/{doc_name}/{page}",
    } <= paths
