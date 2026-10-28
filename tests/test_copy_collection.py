"""Copying the doc agent's collection to Qdrant Cloud, tried between two in-memory Qdrants."""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from copilot.deploy.qdrant import copy_collection


def _source(points: int) -> QdrantClient:
    client = QdrantClient(":memory:")
    client.create_collection(
        "pages",
        vectors_config={"dense": models.VectorParams(size=4, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    client.upsert(
        "pages",
        points=[
            models.PointStruct(
                id=i,
                vector={
                    "dense": [1.0, float(i), 0.5, 0.25],
                    "bm25": models.SparseVector(indices=[i, 100 + i], values=[1.0, 0.5]),
                },
                payload={"doc_name": f"DOC_{i}", "page": i},
            )
            for i in range(points)
        ],
    )
    return client


def test_points_are_copied_with_their_vectors_and_payloads() -> None:
    source, target = _source(10), QdrantClient(":memory:")
    seen: list[int] = []

    assert copy_collection(source, target, "pages", batch=3, progress=seen.append) == 10

    assert target.count("pages", exact=True).count == 10
    assert seen == [3, 6, 9, 10]
    (point,) = target.retrieve("pages", [7], with_payload=True, with_vectors=True)
    assert point.payload == {"doc_name": "DOC_7", "page": 7}
    assert isinstance(point.vector, dict)
    sparse = point.vector["bm25"]
    assert isinstance(sparse, models.SparseVector)
    assert sparse.indices == [7, 107]
    params = target.get_collection("pages").config.params
    assert isinstance(params.vectors, dict)
    assert params.vectors["dense"].size == 4


def test_a_complete_copy_is_left_alone_and_a_partial_one_is_finished() -> None:
    source, target = _source(5), QdrantClient(":memory:")
    copy_collection(source, target, "pages")

    assert copy_collection(source, target, "pages") == 0

    source.upsert(
        "pages",
        points=[models.PointStruct(id=99, vector={"dense": [0.1, 0.2, 0.3, 0.4]}, payload={})],
    )
    assert copy_collection(source, target, "pages") == 6  # upserts are idempotent
    assert target.count("pages", exact=True).count == 6
