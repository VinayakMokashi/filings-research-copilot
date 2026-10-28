"""The ingestion worker: Pub/Sub's envelope, the acknowledgements, and one filing indexed
into an in-memory Qdrant with stand-in models."""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray
from qdrant_client import QdrantClient

from copilot.config import Settings
from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import SparseVector
from copilot.ingest.index import IndexSpec, ensure_collection
from copilot.ingest.jobs import JobResult
from copilot.ingest.pdf import Page
from copilot.worker.app import create_app, read_request
from copilot.worker.ingest import Ingester, IngestRequest

REQUEST = {
    "doc_name": "ACME_2024_10K",
    "url": "https://www.sec.gov/Archives/edgar/data/1/acme-2024.pdf",
    "company": "Acme",
    "doc_type": "10k",
    "doc_period": 2024,
}


def envelope(body: Any) -> dict[str, Any]:
    data = base64.b64encode(json.dumps(body).encode()).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "s"}


def test_a_request_is_read_from_its_envelope() -> None:
    request = read_request(envelope(REQUEST))

    assert request.doc_name == "ACME_2024_10K"
    assert request.document().doc_link == REQUEST["url"]
    with pytest.raises(ValueError, match="ValidationError"):
        read_request(envelope(REQUEST | {"url": "http://example.com/a.pdf"}))
    with pytest.raises(ValueError, match="ValidationError"):
        read_request(envelope(REQUEST | {"doc_name": "../etc/passwd"}))
    with pytest.raises(ValueError, match="KeyError"):
        read_request({"message": {}})


def test_the_status_code_is_the_acknowledgement() -> None:
    handled: list[str] = []

    def handler(request: IngestRequest) -> JobResult:
        if request.doc_name == "BROKEN_2024_10K":
            raise RuntimeError("the parser failed")
        handled.append(request.doc_name)
        return JobResult(request.doc_name, 3, 3, 0.1)

    with TestClient(create_app(handler, Settings(git_sha="abc123"))) as client:
        assert client.post("/pubsub/ingest", json=envelope(REQUEST)).status_code == 204
        assert client.post("/pubsub/ingest", json={"message": {}}).status_code == 400
        assert client.post("/pubsub/ingest", content=b"not json").status_code == 400
        broken = envelope(REQUEST | {"doc_name": "BROKEN_2024_10K"})
        assert client.post("/pubsub/ingest", json=broken).status_code == 500
        assert client.get("/healthz").json() == {"status": "ok", "commit": "abc123"}

    assert handled == ["ACME_2024_10K"]


class _Sparse:
    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [SparseVector(indices=[len(t) % 50], values=[1.0]) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        return SparseVector(indices=[0], values=[1.0])


def _dense(batch: Sequence[Chunk]) -> NDArray[np.float32]:
    return np.ones((len(batch), 4), dtype=np.float32)


def _words(text: str) -> list[tuple[int, int]]:
    spans, start = [], None
    for i, ch in enumerate(text + " "):
        if ch.isspace():
            if start is not None:
                spans.append((start, i))
                start = None
        elif start is None:
            start = i
    return spans


def test_a_filing_is_indexed_once_however_often_it_arrives(tmp_path: Path) -> None:
    client = QdrantClient(":memory:")
    ensure_collection(client, IndexSpec("page", "bge-small", 4))  # fb_page_bge-small
    stored: dict[str, bytes] = {}

    def parse(path: Path, doc_name: str, doc_type: str) -> list[Page]:
        assert path.read_bytes().startswith(b"%PDF")
        return [
            Page(doc_name, 0, "Item 7. Revenue rose on higher volumes.", None, ()),
            Page(doc_name, 1, "Item 8. Financial statements follow.", None, ()),
        ]

    ingest = Ingester(
        Settings(data_dir=tmp_path),
        client=client,
        fetch=lambda url, agent: b"%PDF-1.7 a stand-in",
        store=lambda name, data: stored.__setitem__(name, data),
        parse=parse,
        embed=_dense,
        sparse=_Sparse(),
        offsets=_words,
    )
    request = IngestRequest.model_validate(REQUEST)

    first = ingest(request)
    again = ingest(request)

    assert (first.doc_name, first.chunks, first.added) == ("ACME_2024_10K", 2, 2)
    assert (again.chunks, again.added) == (2, 0)
    assert client.count("fb_page_bge-small", exact=True).count == 2
    assert list(stored) == ["ACME_2024_10K.pdf"]
