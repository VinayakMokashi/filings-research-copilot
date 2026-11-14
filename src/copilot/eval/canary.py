"""The daily canary (step 9.3, ADR-0036): some of the project's own questions through the
live API every day, so that the answer bandit has rewards to learn from, and the deployed
service is checked end to end.

- **The questions** are the routing set's dev questions on the doc route, in id order.
  Each day takes the next `PER_DAY` of them, wrapping round, counted from `FIRST_DAY`.
- **Each is asked in a new conversation,** so the API's answer cache is bypassed, and
  marked `X-Canary: 1`, so the API's judge scores every answer one of the bandit's arms
  writes and reports it in a `reward` event.
- **A day keeps metrics only:** for each question its id, the route, the arm and its group,
  whether it answered, the judge's verdict, the retrieval similarity and the seconds; and a
  summary, with the drift checks of `copilot.eval.drift` when the history is given.
- **A failed request** (an HTTP error, an `error` event, or no answer) fails the day. A
  busy API is noted, not failed: a visitor's question was running.
"""

from __future__ import annotations

import statistics
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import httpx

from copilot.api.client import parse_sse
from copilot.eval.routing import RoutingQuery

FIRST_DAY = date(2026, 11, 16)
PER_DAY = 10
TIMEOUT_S = 300.0
VISITOR = "canary"  # its own daily quota at the API
BUSY = "busy"


def doc_questions(queries: Sequence[RoutingQuery]) -> list[RoutingQuery]:
    """The dev questions on the doc route, in id order."""
    return sorted((q for q in queries if q.route == "doc" and q.split == "dev"), key=lambda q: q.id)


def todays(
    questions: Sequence[RoutingQuery],
    day: date,
    per_day: int = PER_DAY,
    first: date = FIRST_DAY,
) -> list[RoutingQuery]:
    """The day's questions: the next `per_day`, wrapping round the list."""
    if not questions:
        return []
    start = ((day - first).days * per_day) % len(questions)
    return [questions[(start + offset) % len(questions)] for offset in range(per_day)]


def ask(http: httpx.Client, question: RoutingQuery) -> dict[str, Any]:
    """One question through the API, as the canary; its row of metrics."""
    row: dict[str, Any] = {"id": question.id, "ok": False, "error": None}
    body = {"question": question.query, "thread_id": uuid.uuid4().hex[:12]}
    headers = {"X-Canary": "1", "X-Visitor-ID": VISITOR}
    started = time.perf_counter()
    try:
        with http.stream("POST", "/v1/ask", json=body, headers=headers, timeout=TIMEOUT_S) as reply:
            if reply.status_code != 200:
                row["error"] = f"HTTP {reply.status_code}"
            else:
                read(parse_sse(reply.iter_lines()), row)
    except httpx.HTTPError as exc:
        row["error"] = type(exc).__name__
    row["seconds"] = round(time.perf_counter() - started, 2)
    return row


def read(events: Any, row: dict[str, Any]) -> None:
    """Fill `row` from a run's events; an `error` event or a missing answer is a failure."""
    for event in events:
        data = event.data
        if event.kind == "event" and data.get("event") == "route":
            row["route"] = data.get("route")
        elif event.kind == "event" and data.get("event") == "answer":  # the doc or hybrid node
            row["similarity"] = data.get("similarity")
        elif event.kind == "event" and data.get("event") == "reward":
            row |= {
                "arm": data.get("arm"),
                "assignment": data.get("assignment"),
                "judged": bool(data.get("judged")),
                "faithful": data.get("faithful"),
            }
        elif event.kind == "response":
            row |= {
                "answered": bool(data.get("answered")),
                "cached": bool(data.get("cached")),
                "arm": row.get("arm", data.get("arm")),
                "route": data.get("route", row.get("route")),
            }
        elif event.kind == "error":
            message = str(data.get("error", ""))
            row["error"] = BUSY if "busy" in message else "error event"
    if row["error"] is None and "answered" not in row:
        row["error"] = "no answer"
    row["ok"] = row["error"] is None


def failed(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The requests that failed the day; a busy API isn't one."""
    return [row for row in rows if not row["ok"] and row.get("error") != BUSY]


def summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A day's numbers."""
    answered = [row for row in rows if row["ok"]]
    judged = [row for row in answered if row.get("judged")]
    seconds = sorted(float(row["seconds"]) for row in answered)
    return {
        "questions": len(rows),
        "ok": len(answered),
        "failed": len(failed(rows)),
        "busy": sum(row.get("error") == BUSY for row in rows),
        "answered": sum(bool(row.get("answered")) for row in answered),
        "routes": dict(Counter(str(row.get("route")) for row in answered)),
        "arms": dict(Counter(str(row.get("arm")) for row in answered)),
        "groups": dict(Counter(str(row.get("assignment")) for row in answered)),
        "judged": len(judged),
        "faithful": sum(bool(row.get("faithful")) for row in judged),
        "median_seconds": round(statistics.median(seconds), 2) if seconds else None,
        "max_seconds": seconds[-1] if seconds else None,
    }
