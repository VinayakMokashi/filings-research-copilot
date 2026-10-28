"""What the deployment on Google Cloud runs with (ADR-0031): Firestore for the API's state,
ID tokens between services, visitors by address, and the switches for files.

Firestore is replaced by a small in-memory stand-in with the same calls, so these tests
need no cloud.
"""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from google.cloud.firestore import Increment
from pydantic import SecretStr

from copilot.agents.build import model_client
from copilot.answer.agent import corpus_documents, corpus_filings
from copilot.api.client import CopilotClient, GoogleIdToken, visitor_from_forwarded
from copilot.api.firestore import FirestoreCache, FirestoreFeedback, FirestoreQuotas
from copilot.api.quotas import Verdict
from copilot.api.services import Feedback, readiness
from copilot.config import Settings
from copilot.llm import LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.mcp.server import build_parser, transport_security


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class _Document:
    def __init__(self, db: FakeFirestore, path: str) -> None:
        self.db, self.path = db, path

    def get(self) -> _Snapshot:
        return _Snapshot(self.db.docs.get(self.path))

    def set(self, data: Mapping[str, Any], merge: bool = False) -> None:
        self.db.write(self.path, data, merge)

    def collection(self, name: str) -> _Collection:
        return _Collection(self.db, f"{self.path}/{name}")


class _Collection:
    def __init__(self, db: FakeFirestore, path: str) -> None:
        self.db, self.path = db, path

    def document(self, doc_id: str | None = None) -> _Document:
        return _Document(self.db, f"{self.path}/{doc_id or uuid.uuid4().hex}")


class _Batch:
    def __init__(self, db: FakeFirestore) -> None:
        self.db = db
        self.writes: list[tuple[str, Mapping[str, Any], bool]] = []

    def set(self, doc: _Document, data: Mapping[str, Any], merge: bool = False) -> None:
        self.writes.append((doc.path, data, merge))

    def commit(self) -> None:
        for write in self.writes:
            self.db.write(*write)


class FakeFirestore:
    """Documents by path, with merges and Firestore's `Increment`."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> _Collection:
        return _Collection(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)

    def write(self, path: str, data: Mapping[str, Any], merge: bool) -> None:
        current = dict(self.docs.get(path) or {}) if merge else {}
        for key, value in data.items():
            if isinstance(value, Increment):
                current[key] = current.get(key, 0) + value.value
            else:
                current[key] = value
        self.docs[path] = current


DAY = date(2026, 10, 28)
NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_quotas_count_each_visitor_and_everyone() -> None:
    db = FakeFirestore()
    quotas = FirestoreQuotas(db)

    assert quotas.take("a", DAY, per_visitor=2, total=3).allowed
    assert quotas.take("a", DAY, per_visitor=2, total=3).allowed
    assert quotas.take("a", DAY, per_visitor=2, total=3) == Verdict(False, "visitor")
    assert quotas.take("b", DAY, per_visitor=2, total=3).allowed
    assert quotas.take("c", DAY, per_visitor=2, total=3) == Verdict(False, "total")
    assert quotas.take("c", DAY + timedelta(days=1), per_visitor=2, total=3).allowed

    assert db.docs["quotas/2026-10-28"]["questions"] == 3
    assert db.docs["quotas/2026-10-28/visitors/a"]["questions"] == 2
    assert db.docs["quotas/2026-10-28/visitors/a"]["expires_at"] == datetime(
        2026, 10, 31, tzinfo=UTC
    )


def test_cached_answers_keep_their_rows_and_expire() -> None:
    db = FakeFirestore()
    cache = FirestoreCache(db, timedelta(days=7))
    response = {"answered": True, "data": {"rows": [[1577.0, "3M"], [1347.0, "Coca-Cola"]]}}

    cache.put("What was 3M's capex?", response, NOW)
    found = cache.get("what was 3m's capex", NOW + timedelta(days=1))

    assert found is not None
    assert found.response == response
    assert cache.get("What was 3M's capex?", NOW + timedelta(days=7)) is None
    (stored,) = db.docs.values()
    assert isinstance(stored["response"], str)  # rows in rows can't be stored as arrays
    assert stored["expires_at"] == NOW + timedelta(days=7)
    assert cache.get("Another question", NOW) is None


def test_feedback_is_one_document_per_rating() -> None:
    db = FakeFirestore()
    store = FirestoreFeedback(db)

    assert store.add(Feedback("t1", 1, "up", "", "r1")) == 1
    assert store.add(Feedback("t1", 2, "down", "wrong year", None)) == 2
    ratings = sorted(doc["rating"] for doc in db.docs.values())
    assert ratings == ["down", "up"]


def _jwt(exp: float) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.signature"


def test_id_tokens_are_reused_until_five_minutes_before_they_expire() -> None:
    now = [1_000.0]
    fetched: list[str] = []

    def fetch(audience: str) -> str:
        fetched.append(audience)
        return _jwt(now[0] + 3600)

    auth = GoogleIdToken("https://api.example", fetch=fetch, clock=lambda: now[0])
    first = auth.token()
    now[0] += 3000
    assert auth.token() == first
    now[0] += 400  # within five minutes of the expiry
    auth.token()

    assert fetched == ["https://api.example", "https://api.example"]


def test_the_client_signs_every_call_to_the_api() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"ready": True})

    auth = GoogleIdToken("https://api.example", fetch=lambda audience: "a.b.c")
    client = CopilotClient(
        "https://api.example", "visitor-1", transport=httpx.MockTransport(handler), auth=auth
    )
    client.ready()

    assert seen == ["Bearer a.b.c"]


def test_a_visitor_is_the_address_googles_front_end_saw() -> None:
    mine = visitor_from_forwarded({"X-Forwarded-For": "203.0.113.7"}, "session-1")

    # A forged entry in front doesn't change who it is: the last entry counts.
    assert visitor_from_forwarded({"x-forwarded-for": "1.1.1.1, 203.0.113.7"}, "s2") == mine
    assert len(mine) == 32
    assert "203.0.113.7" not in mine
    assert visitor_from_forwarded({}, "session-1") == "session-1"


def test_a_deployed_mcp_server_accepts_its_own_address(monkeypatch: pytest.MonkeyPatch) -> None:
    security = transport_security(["mcp-123.asia-south1.run.app"])

    assert "mcp-123.asia-south1.run.app" in security.allowed_hosts
    assert "https://mcp-123.asia-south1.run.app" in security.allowed_origins
    monkeypatch.setenv("PORT", "8080")
    assert build_parser().parse_args([]).port == 8080


def test_the_corpus_comes_from_its_manifest_when_there_is_one(tmp_path: Path) -> None:
    rows = [
        {"doc_name": "BETA_2020_10K", "company": "Beta", "doc_period": 2020},
        {"doc_name": "ALPHA_2019_10K", "company": "Alpha", "doc_period": 2019},
    ]
    manifest = tmp_path / "processed" / "corpus.jsonl"
    manifest.parent.mkdir()
    manifest.write_text(
        "\n".join(
            json.dumps(row | {"gics_sector": "Industrials", "doc_type": "10k", "doc_link": "x"})
            for row in rows
        ),
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path)

    assert [d.doc_name for d in corpus_documents(settings)] == ["ALPHA_2019_10K", "BETA_2020_10K"]
    assert [(f.company, f.year) for f in corpus_filings(settings)] == [
        ("Alpha", 2019),
        ("Beta", 2020),
    ]


def test_the_deployment_caches_no_model_calls_on_disk(tmp_path: Path) -> None:
    cached = model_client(Settings(data_dir=tmp_path), "llm.jsonl")
    uncached = model_client(Settings(data_dir=tmp_path, llm_disk_cache=False), "llm.jsonl")

    assert isinstance(cached._client, CachedLLM)
    assert isinstance(uncached._client, LLMGateway)


def test_readiness_reads_the_collection_with_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        calls.append((url, headers))
        return httpx.Response(200)

    monkeypatch.setattr(httpx, "get", fake_get)
    settings = Settings(
        data_dir=tmp_path,
        qdrant_url="https://cluster.example:6333",
        qdrant_api_key=SecretStr("read-only"),
    )

    assert readiness(settings)["qdrant"] is True
    assert calls == [
        ("https://cluster.example:6333/collections/fb_page_bge-small", {"api-key": "read-only"})
    ]
