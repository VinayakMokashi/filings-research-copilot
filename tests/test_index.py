"""The Qdrant index: collection setup, idempotent upserts, resuming and payloads."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from qdrant_client import QdrantClient, models

from copilot.ingest import index
from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import HashingDense, HashingSparse

SPEC = index.IndexSpec("tokens-12", "hashing", 64)
TEXTS = (
    "Revenue grew strongly in every segment",
    "Litigation remains pending in two courts",
    "Capital expenditure fell to 1.2 billion",
    "Dividends were raised for the tenth year",
)


def _chunk(number: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=hashlib.sha256(f"ACME|{number}".encode()).hexdigest(),
        strategy="tokens-12",
        doc_name="ACME_2022_10K",
        chunk_index=number,
        text=text,
        char_start=number * 100,
        char_end=number * 100 + len(text),
        pages=(number + 1, number),
        section="7",
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        tokens=len(text.split()),
    )


CHUNKS = [_chunk(number, text) for number, text in enumerate(TEXTS)]


@pytest.fixture
def client() -> QdrantClient:
    qdrant = QdrantClient(":memory:")
    index.ensure_collection(qdrant, SPEC)
    return qdrant


def _embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
    return HashingDense().embed_documents([chunk.text for chunk in batch])


def test_the_collection_is_created_once_with_named_vectors() -> None:
    qdrant = QdrantClient(":memory:")

    assert SPEC.collection == "fb_tokens-12_hashing"
    assert index.ensure_collection(qdrant, SPEC)
    assert not index.ensure_collection(qdrant, SPEC)
    params = qdrant.get_collection(SPEC.collection).config.params
    assert isinstance(params.vectors, dict)
    assert params.vectors[index.DENSE].size == 64
    assert params.vectors[index.DENSE].distance == models.Distance.COSINE
    assert params.sparse_vectors is not None
    assert params.sparse_vectors[index.SPARSE].modifier == models.Modifier.IDF


def test_index_chunks_adds_only_what_is_missing(client: QdrantClient) -> None:
    sizes: list[int] = []

    def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
        sizes.append(len(batch))
        return _embed(batch)

    sparse = HashingSparse()
    assert index.index_chunks(client, SPEC.collection, CHUNKS[:2], embed, sparse) == 2
    assert index.index_chunks(client, SPEC.collection, CHUNKS, embed, sparse, batch_size=1) == 2
    assert index.index_chunks(client, SPEC.collection, CHUNKS, embed, sparse) == 0
    assert sizes == [2, 1, 1]
    assert index.count(client, SPEC.collection) == len(CHUNKS)


def test_points_carry_the_chunk_and_both_vectors(client: QdrantClient) -> None:
    index.index_chunks(client, SPEC.collection, CHUNKS, _embed, HashingSparse())

    [point] = client.retrieve(
        SPEC.collection, ids=[CHUNKS[2].point_id], with_payload=True, with_vectors=True
    )

    assert point.payload is not None
    assert point.payload["text"] == TEXTS[2]
    assert point.payload["pages"] == [3, 2]
    assert (point.payload["company"], point.payload["doc_period"]) == ("Acme", 2022)
    assert isinstance(point.vector, dict)
    assert set(point.vector) == {index.DENSE, index.SPARSE}


def test_a_hybrid_query_finds_the_matching_chunk(client: QdrantClient) -> None:
    index.index_chunks(client, SPEC.collection, CHUNKS, _embed, HashingSparse())
    query = "capital expenditure"
    sparse = HashingSparse().embed_query(query)

    hits = client.query_points(
        SPEC.collection,
        prefetch=[
            models.Prefetch(
                query=HashingDense().embed_query(query).tolist(), using=index.DENSE, limit=4
            ),
            models.Prefetch(
                query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                using=index.SPARSE,
                limit=4,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=2,
    ).points

    assert hits[0].id == CHUNKS[2].point_id


def test_read_card_returns_none_without_a_card(tmp_path: Path) -> None:
    assert index.read_card(tmp_path, "fb_page_missing") is None
    path = index.card_path(tmp_path, "fb_page_x")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"collection": "fb_page_x"}), encoding="utf-8")

    assert index.read_card(tmp_path, "fb_page_x") == {"collection": "fb_page_x"}


def _stored(tmp_path: Path, chunks: Sequence[Chunk], vectors: NDArray[np.float32]) -> Path:
    path = tmp_path / "vectors" / "tuned.npy"
    path.parent.mkdir()
    np.save(path, vectors)
    (path.parent / "chunk_ids.json").write_text(
        json.dumps([chunk.chunk_id for chunk in chunks]), encoding="utf-8"
    )
    return path


def test_stored_vectors_look_up_rows_by_chunk_and_check_against_a_model(tmp_path: Path) -> None:
    chunks = [_chunk(number, text) for number, text in enumerate(TEXTS)]
    model = HashingDense()
    stored = index.StoredVectors(_stored(tmp_path, chunks, model.embed_documents(TEXTS)))

    assert np.array_equal(
        stored([chunks[2], chunks[0]]), model.embed_documents([TEXTS[2], TEXTS[0]])
    )
    assert stored.check(model, chunks) == 0.0
    assert stored.check(HashingDense(key="other", dim=64), chunks[:1]) == 0.0
    with pytest.raises(KeyError, match="no vectors for 1"):
        stored([_chunk(9, "Goodwill was impaired")])


def test_stored_vectors_refuse_a_file_whose_ids_dont_match(tmp_path: Path) -> None:
    chunks = [_chunk(number, text) for number, text in enumerate(TEXTS)]
    path = _stored(tmp_path, chunks[:3], HashingDense().embed_documents(TEXTS))

    with pytest.raises(ValueError, match="4 rows for 3 chunk ids"):
        index.StoredVectors(path)
