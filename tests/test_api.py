"""The API: streamed answers, feedback, second answers and picks, the answer bandit's
rewards, cited pages, health checks and request ids."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from copilot.answer.bandit import MemoryArmStats, OnlineChooser
from copilot.api import app as api
from copilot.api.bandit import MemoryBanditLog, OnlineBandit
from copilot.api.cache import MemoryCache
from copilot.api.services import Asker, MemoryFeedback, MemoryPreferences, Services
from copilot.ingest.pdf import Page, write_pages
from copilot.llm import FakeLLM
from copilot.llm.fallback import MemorySpend
from copilot.retrieval.query import Filing

QUESTION = "What was 3M's capital expenditure in fiscal 2018?"


PAGE_TEXT = "Purchases of PP&E were $1,577 million."
SOURCE = {"number": 1, "label": "3M, PDF page 2", "doc_name": "3M_2018_10K", "page": 1}


class FakeCopilot:
    """Yields what the runner yields for a doc question; can fail mid-run like the graph.

    `arm` and `assignment` say which arm the run's answer is written by; a second answer
    (`avoid_arm`) is always written by `fast`.
    """

    def __init__(
        self,
        fail: Exception | None = None,
        answered: bool = True,
        arm: str | None = None,
        assignment: str | None = None,
    ) -> None:
        self.fail = fail
        self.answered = answered
        self.arm = arm
        self.assignment = assignment
        self.calls: list[tuple[str, str, str]] = []
        self.routes: list[str | None] = []
        self.avoided: list[str | None] = []
        self.recorded: list[tuple[str, dict[str, Any]]] = []
        self.written: dict[str, tuple[str | None, str | None]] = {}

    def record(self, thread_id: str, turn: Any) -> None:
        self.recorded.append((thread_id, dict(turn)))

    def details(self, thread_id: str) -> dict[str, Any]:
        arm, assignment = self.written.get(thread_id, (None, None))
        result: dict[str, Any] = {
            "kind": "doc",
            "answer": {
                "sources": [SOURCE | {"text": PAGE_TEXT, "tokens": 9}],
                "calculations": [],
            },
        }
        if arm is not None:
            result |= {"arm": arm, "assignment": assignment}
        return {"result": result, "validation": {}, "revisions": 0, "decision": {}, "draft": None}

    def stream(
        self,
        question: str,
        *,
        thread_id: str,
        user_id: str = "default",
        route: str | None = None,
        avoid_arm: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        self.calls.append((question, thread_id, user_id))
        self.routes.append(route)
        self.avoided.append(avoid_arm)
        written = ("fast", "retry") if avoid_arm else (self.arm, self.assignment)
        self.written[thread_id] = written
        base = {"thread": thread_id, "turn": 1}
        yield base | {"type": "start", "node": "route"}
        yield base | {"type": "event", "event": "route", "route": "doc"}
        yield base | {"type": "end", "node": "route", "ms": 3.0, "error": None}
        if self.fail is not None:
            yield base | {"type": "error", "error": "RuntimeError: boom"}
            raise self.fail
        usage = {"groq/openai/gpt-oss-120b": [1000, 200]}
        yield base | {"type": "event", "event": "usage", "tokens_by_model": usage}
        reply = {
            "question": question,
            "standalone": question,
            "text": "Capex was $1,577 million [1].",
            "route": "data",
            "answered": self.answered,
            "citations": [SOURCE],
            "arm": written[0],
        }
        yield base | {"type": "response", **reply}


class BrokenCopilot:
    """Fails before the graph starts, so no error event comes from the runner."""

    def record(self, thread_id: str, turn: Any) -> None:
        raise AssertionError("nothing to record")

    def details(self, thread_id: str) -> dict[str, Any]:
        raise AssertionError("no run to read")

    def stream(
        self,
        question: str,
        *,
        thread_id: str,
        user_id: str = "default",
        route: str | None = None,
        avoid_arm: str | None = None,
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
        assert client.get("/health").json() == {"status": "ok", "commit": "unknown"}
        ready = client.get("/ready")
        assert (ready.status_code, ready.json()["ready"]) == (200, True)

    not_ready = make_services(tmp_path / "b", checks=lambda: {"qdrant": False, "llm_key": True})
    with TestClient(api.create_app(not_ready)) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"ready": False, "checks": {"qdrant": False, "llm_key": True}}


def test_a_question_streams_the_graphs_events(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        response = client.post("/v1/ask", json={"question": f"  {QUESTION} "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse(response.text)
    kinds = ["meta", "start", "event", "end", "event", "response", "done"]
    assert [kind for kind, _ in events] == kinds
    meta = events[0][1]
    assert meta["request_id"] == response.headers["x-request-id"]
    assert len(meta["thread_id"]) == 12
    assert events[5][1]["text"] == "Capex was $1,577 million [1]."
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    assert copilot.calls == [(QUESTION, meta["thread_id"], f"anon-{meta['thread_id']}")]


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
        "/health",
        "/ready",
        "/v1/ask",
        "/v1/brief",
        "/v1/feedback",
        "/v1/preference",
        "/v1/sources/{doc_name}/{page}",
    } <= paths
    # Cloud Run's front end answers /healthz itself, and Google advises against paths
    # ending in "z": such a path would never reach the container.
    assert not [path for path in paths if path.endswith("z")]


def test_a_visitor_over_the_daily_quota_gets_a_429(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    services.per_visitor, services.total = 2, 100
    ask = {"question": QUESTION}
    first = {"X-Visitor-ID": "visitor-0001"}
    with TestClient(api.create_app(services)) as client:
        allowed = [client.post("/v1/ask", json=ask, headers=first).status_code for _ in range(2)]
        refused = client.post("/v1/ask", json=ask, headers=first)
        other = client.post("/v1/ask", json=ask, headers={"X-Visitor-ID": "visitor-0002"})

    assert allowed == [200, 200]
    assert refused.status_code == 429
    assert "your" in refused.json()["detail"]
    assert 0 < int(refused.headers["retry-after"]) <= 86_400
    assert other.status_code == 200


def test_the_total_quota_holds_for_everyone(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    services.per_visitor, services.total = 10, 2
    ask = {"question": QUESTION}
    with TestClient(api.create_app(services)) as client:
        codes = [
            client.post(
                "/v1/ask", json=ask, headers={"X-Visitor-ID": f"visitor-000{n}"}
            ).status_code
            for n in range(3)
        ]
        refused = client.post("/v1/ask", json=ask, headers={"X-Visitor-ID": "visitor-0009"})

    assert codes == [200, 200, 429]
    assert "everyone" in refused.json()["detail"]


def test_a_malformed_question_counts_for_nothing(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    services.per_visitor = 1
    headers = {"X-Visitor-ID": "visitor-0001"}
    with TestClient(api.create_app(services)) as client:
        assert client.post("/v1/ask", json={"question": " "}, headers=headers).status_code == 422
        assert (
            client.post("/v1/ask", json={"question": QUESTION}, headers=headers).status_code == 200
        )


def with_cache(tmp_path: Path, copilot: FakeCopilot | None = None) -> Services:
    services = make_services(tmp_path, copilot=copilot)
    services.cache = MemoryCache(timedelta(days=7))
    return services


def test_a_repeated_question_is_answered_from_the_cache(tmp_path: Path) -> None:
    services = with_cache(tmp_path)
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    with TestClient(api.create_app(services)) as client:
        client.post("/v1/ask", json={"question": QUESTION})
        again = sse(client.post("/v1/ask", json={"question": f"  {QUESTION.upper()}  "}).text)

    assert len(copilot.calls) == 1
    assert [kind for kind, _ in again] == ["meta", "event", "response", "done"]
    assert again[1][1]["event"] == "cache"
    assert again[2][1]["cached"] is True
    assert again[2][1]["text"] == "Capex was $1,577 million [1]."
    thread = again[0][1]["thread_id"]
    assert copilot.recorded == [
        (
            thread,
            {
                "question": QUESTION.upper(),
                "standalone": QUESTION,  # as the stored answer read it
                "route": "data",
                "answer": "Capex was $1,577 million [1].",
            },
        )
    ]


def test_follow_ups_and_named_users_are_never_cached(tmp_path: Path) -> None:
    services = with_cache(tmp_path)
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    with TestClient(api.create_app(services)) as client:
        client.post("/v1/ask", json={"question": QUESTION, "thread_id": "t-1"})
        client.post("/v1/ask", json={"question": QUESTION, "user_id": "u1"})
        client.post("/v1/ask", json={"question": QUESTION})  # the first anonymous one: stored
        client.post("/v1/ask", json={"question": QUESTION, "user_id": "u1"})

    assert len(copilot.calls) == 4


def test_an_unanswered_question_is_not_stored(tmp_path: Path) -> None:
    services = with_cache(tmp_path, copilot=FakeCopilot(answered=False))
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    with TestClient(api.create_app(services)) as client:
        for _ in range(2):
            client.post("/v1/ask", json={"question": QUESTION})

    assert len(copilot.calls) == 2


def test_a_cached_answer_costs_no_quota(tmp_path: Path) -> None:
    services = with_cache(tmp_path)
    services.per_visitor = 1
    headers = {"X-Visitor-ID": "visitor-0001"}
    with TestClient(api.create_app(services)) as client:
        first = client.post("/v1/ask", json={"question": QUESTION}, headers=headers)
        repeat = client.post("/v1/ask", json={"question": QUESTION}, headers=headers)
        new = client.post("/v1/ask", json={"question": "What was 3M's revenue?"}, headers=headers)

    assert (first.status_code, repeat.status_code, new.status_code) == (200, 200, 429)


def test_a_brief_asks_for_the_brief_route(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    with TestClient(api.create_app(services)) as client:
        events = sse(client.post("/v1/brief", json={"question": "Brief on 3M's 2022."}).text)
        client.post("/v1/ask", json={"question": QUESTION})

    kinds = [kind for kind, _ in events]
    assert (kinds[0], kinds[-1]) == ("meta", "done")
    assert copilot.routes == ["brief", None]


def test_a_brief_and_an_answer_to_the_same_words_are_stored_apart(tmp_path: Path) -> None:
    services = with_cache(tmp_path)
    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    with TestClient(api.create_app(services)) as client:
        client.post("/v1/ask", json={"question": QUESTION})
        brief = sse(client.post("/v1/brief", json={"question": QUESTION}).text)
        again = sse(client.post("/v1/brief", json={"question": QUESTION}).text)

    assert copilot.routes == [None, "brief"]
    assert all(data.get("event") != "cache" for _, data in brief)
    assert again[1][1]["event"] == "cache"


def asked(client: TestClient, body: dict[str, Any], **headers: str) -> list[tuple[str, Any]]:
    return sse(client.post("/v1/ask", json=body, headers=headers).text)


def test_an_answer_is_remembered_with_what_produced_it(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        events = asked(client, {"question": QUESTION})

    request_id = events[0][1]["request_id"]
    exchange = services.exchanges.get(request_id)
    assert exchange is not None
    assert (exchange["question"], exchange["standalone"], exchange["kind"]) == (
        QUESTION,
        QUESTION,
        "doc",
    )
    assert exchange["text"] == "Capex was $1,577 million [1]."
    assert exchange["sources"] == [SOURCE | {"text": PAGE_TEXT}]
    assert exchange["models"] == {"groq/openai/gpt-oss-120b": [1000, 200]}
    assert exchange["cost_usd"] is not None
    assert (exchange["arm"], exchange["cached"], exchange["canary"]) == (None, False, False)


def test_a_rating_keeps_the_exchange_it_rates(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        meta = asked(client, {"question": QUESTION})[0][1]
        rating = {"thread_id": meta["thread_id"], "turn": 1, "rating": "down"}
        client.post("/v1/feedback", json=rating | {"request_id": meta["request_id"]})
        client.post("/v1/feedback", json=rating | {"request_id": "long-gone"})

    feedback = services.feedback
    assert isinstance(feedback, MemoryFeedback)
    (_, kept, exchange), (_, _, missing) = feedback.records
    assert kept.rating == "down"
    assert exchange is not None
    assert exchange["request_id"] == meta["request_id"]
    assert missing is None  # the rating alone, when the exchange is no longer held


def test_a_cached_answer_is_remembered_too(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    services.cache = MemoryCache(timedelta(days=7))
    with TestClient(api.create_app(services)) as client:
        asked(client, {"question": QUESTION})
        meta = asked(client, {"question": QUESTION})[0][1]

    exchange = services.exchanges.get(meta["request_id"])
    assert exchange is not None
    assert exchange["cached"] is True
    assert exchange["sources"] == []  # a stored answer keeps no sources


def test_a_second_answer_reads_the_first_ones_question_in_a_new_conversation(
    tmp_path: Path,
) -> None:
    services = make_services(tmp_path)
    services.cache = MemoryCache(timedelta(days=7))
    with TestClient(api.create_app(services)) as client:
        first = asked(client, {"question": QUESTION})[0][1]
        events = asked(client, {"question": QUESTION, "retry_of": first["request_id"]})

    copilot = services.copilot
    assert isinstance(copilot, FakeCopilot)
    second = events[0][1]
    assert len(copilot.calls) == 2  # a second answer is never served from the cache
    assert second["thread_id"] != first["thread_id"]
    assert copilot.calls[1][:2] == (QUESTION, second["thread_id"])
    assert copilot.routes == [None, "data"]  # the first answer's route
    assert copilot.avoided == [None, "strong"]  # the fixed arm wrote the first
    exchange = services.exchanges.get(second["request_id"])
    assert exchange is not None
    assert (exchange["retry_of"], exchange["arm"]) == (first["request_id"], "fast")
    cache = services.cache
    assert isinstance(cache, MemoryCache)
    assert len(cache.entries) == 1  # nor stored there


def test_a_second_answer_to_an_answer_no_longer_held_is_refused_first(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    services.per_visitor = 1
    with TestClient(api.create_app(services)) as client:
        gone = client.post("/v1/ask", json={"question": QUESTION, "retry_of": "long-gone"})
        still_allowed = client.post("/v1/ask", json={"question": QUESTION})
        brief = client.post("/v1/brief", json={"question": QUESTION, "retry_of": "long-gone"})

    assert gone.status_code == 404
    assert "no longer held" in gone.json()["detail"]
    assert still_allowed.status_code == 200  # the refusal took none of the quota
    assert brief.status_code == 422


def test_a_pick_between_two_answers_keeps_both(tmp_path: Path) -> None:
    services = make_services(tmp_path)
    with TestClient(api.create_app(services)) as client:
        first = asked(client, {"question": QUESTION})[0][1]["request_id"]
        second = asked(client, {"question": QUESTION, "retry_of": first})[0][1]["request_id"]
        pick = {"first": first, "second": second, "chosen": "second", "comment": " sharper "}
        kept = client.post("/v1/preference", json=pick)
        gone = client.post("/v1/preference", json=pick | {"second": "long-gone"})
        bad = client.post("/v1/preference", json=pick | {"chosen": "both"})

    assert (kept.status_code, kept.json()) == (201, {"id": 1})
    assert (gone.status_code, bad.status_code) == (404, 422)
    preferences = services.preferences
    assert isinstance(preferences, MemoryPreferences)
    ((_, preference),) = preferences.records
    assert (preference.chosen, preference.comment) == ("second", "sharper")
    assert preference.first["request_id"] == first
    assert preference.second["retry_of"] == first


PASS = '{"sentences": [{"n": 1, "supported": true, "supporting": [1]}]}'


def bandit(judge: FakeLLM, share: float = 0.0) -> OnlineBandit:
    chooser = OnlineChooser(MemoryArmStats(), MemorySpend(), 0.25, FakeLLM([]), seed=0)
    return OnlineBandit(chooser, judge, MemoryBanditLog(), judge_share=share, seed=0)


def test_the_bandit_judges_every_canary_answer_an_arm_wrote(tmp_path: Path) -> None:
    services = make_services(tmp_path, copilot=FakeCopilot(arm="fast", assignment="policy"))
    judge = FakeLLM([PASS])
    services.bandit = bandit(judge)
    with TestClient(api.create_app(services)) as client:
        visitor = asked(client, {"question": QUESTION})
        canary = asked(client, {"question": QUESTION}, **{"X-Canary": "1"})

    reward = [data for kind, data in canary if kind == "event" and data.get("event") == "reward"]
    assert reward == [
        {
            "type": "event",
            "event": "reward",
            "arm": "fast",
            "assignment": "policy",
            "judged": True,
            "faithful": True,
            "reward": 1.0,
        }
    ]
    assert canary[-1][0] == "done"  # the reward comes before the stream ends
    visitor_reward = [d for k, d in visitor if k == "event" and d.get("event") == "reward"]
    assert visitor_reward[0]["judged"] is False  # a visitor's share of 0
    assert len(judge.calls) == 1
    assert services.bandit.chooser.stats.read() == ({"fast": 1}, {"fast": 1.0})
    log = services.bandit.log
    assert isinstance(log, MemoryBanditLog)
    assert [record["canary"] for record in log.records.values()] == [False, True]


def test_a_rating_rewards_the_arm_that_wrote_the_answer_once(tmp_path: Path) -> None:
    services = make_services(tmp_path, copilot=FakeCopilot(arm="strong-low", assignment="control"))
    services.bandit = bandit(FakeLLM([]))
    with TestClient(api.create_app(services)) as client:
        meta = asked(client, {"question": QUESTION})[0][1]
        rating = {"thread_id": meta["thread_id"], "rating": "up", "request_id": meta["request_id"]}
        client.post("/v1/feedback", json=rating)
        client.post("/v1/feedback", json=rating)

    assert services.bandit.chooser.stats.read() == ({"strong-low": 1}, {"strong-low": 1.0})
