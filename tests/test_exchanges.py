"""What the API remembers of each answer it served (step 9.2, ADR-0035)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from copilot.api.exchanges import ExchangeLog, exchange_record, usage_of
from copilot.llm.gateway import token_cost

NOW = datetime(2026, 11, 16, 9, 30, tzinfo=UTC)
RESPONSE = {
    "type": "response",
    "turn": 2,
    "question": "And in fiscal 2022?",
    "standalone": "What did Acme spend on new plants in fiscal 2022?",
    "route": "doc",
    "text": "Acme spent $420 million on new plants [1].",
    "answered": True,
    "citations": [
        {"number": 1, "label": "Acme, PDF page 41", "doc_name": "ACME_2022_10K", "page": 40}
    ],
    "validation": {"checked": True, "faithful": True, "revisions": 1},
}
SOURCE = {
    "number": 1,
    "label": "Acme, PDF page 41",
    "doc_name": "ACME_2022_10K",
    "page": 40,
    "text": "Acme built two plants in fiscal 2022 for $420 million.",
    "tokens": 12,
}


def details(revisions: int = 1) -> dict[str, Any]:
    answer = {
        "text": RESPONSE["text"],
        "sources": [SOURCE],
        "calculations": [{"id": "c1", "expression": "200 + 220", "decimals": 0, "value": 420.0}],
    }
    return {
        "result": {"kind": "doc", "answer": answer, "arm": "fast", "assignment": "policy"},
        "validation": RESPONSE["validation"],
        "revisions": revisions,
        "decision": {"route": "doc"},
        "draft": {"kind": "doc", "answer": {"text": "Acme spent about $0.4 billion [1]."}},
    }


def test_usage_adds_up_each_models_tokens_and_prices_them() -> None:
    events: list[dict[str, Any]] = [
        {
            "type": "event",
            "event": "usage",
            "tokens_by_model": {"groq/openai/gpt-oss-120b": [100, 20]},
        },
        {"type": "event", "event": "route", "route": "doc"},
        {
            "type": "event",
            "event": "usage",
            "tokens_by_model": {"groq/openai/gpt-oss-120b": [50, 5]},
        },
    ]

    tokens, cost = usage_of(events)

    assert tokens == {"groq/openai/gpt-oss-120b": [150, 25]}
    assert cost == pytest.approx(token_cost("groq/openai/gpt-oss-120b", 150, 25))
    unknown: list[dict[str, Any]] = [
        {"event": "usage", "tokens_by_model": {"nowhere/model": [1, 1]}}
    ]
    assert usage_of(unknown) == ({"nowhere/model": [1, 1]}, None)


def test_an_exchange_holds_the_answer_its_sources_its_arm_and_its_draft() -> None:
    exchange = exchange_record(
        request_id="r2", thread_id="t1", response=RESPONSE, details=details(), events=[], now=NOW
    )

    assert exchange["standalone"] == "What did Acme spend on new plants in fiscal 2022?"
    assert (exchange["route"], exchange["kind"], exchange["turn"]) == ("doc", "doc", 2)
    assert exchange["sources"] == [
        {k: SOURCE[k] for k in ("number", "label", "doc_name", "page", "text")}
    ]
    assert exchange["calculations"] == [{"id": "c1", "expression": "200 + 220", "value": 420.0}]
    assert (exchange["arm"], exchange["assignment"]) == ("fast", "policy")
    assert exchange["draft"] == "Acme spent about $0.4 billion [1]."
    assert exchange["created"] == "2026-11-16T09:30:00+00:00"
    unrevised = exchange_record(
        request_id="r3", thread_id="t1", response=RESPONSE, details=details(0), events=[], now=NOW
    )
    assert unrevised["draft"] is None


def test_an_answer_from_the_cache_keeps_what_its_response_says() -> None:
    cached = RESPONSE | {"cached": True}

    exchange = exchange_record(
        request_id="r4",
        thread_id="t9",
        response=cached,
        details={},
        events=[],
        now=NOW,
        canary=True,
    )

    assert exchange["cached"] is True
    assert exchange["canary"] is True
    assert (exchange["sources"], exchange["arm"], exchange["kind"]) == ([], None, None)
    assert exchange["text"] == RESPONSE["text"]


def test_the_log_keeps_the_newest_exchanges_and_counts_a_claim_once() -> None:
    log = ExchangeLog(size=2)
    for number in (1, 2, 3):
        log.add({"request_id": f"r{number}"})

    assert log.get("r1") is None  # the oldest went first
    assert log.get("r3") == {"request_id": "r3"}
    assert log.get(None) is None
    assert log.claim("r3", "thumbs") is True
    assert log.claim("r3", "thumbs") is False
    assert log.claim("r3", "judge") is True
    assert log.claim("r1", "thumbs") is False  # no longer held
