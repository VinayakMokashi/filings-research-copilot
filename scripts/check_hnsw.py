"""Measure what HNSW gives up against exact search, on a copy of an index (ADR-0010).

At this project's scale Qdrant searches by brute force: a segment builds its HNSW graph only
once its vectors pass the indexing threshold (10 MB), and the main collection's 34 MB of
dense vectors are spread over 8 segments. This script copies a collection's dense vectors
into a scratch collection whose segments all build the graph, runs the dev questions through
exact search and through HNSW at several `hnsw_ef` values, and reports recall@10 against
exact search and the latency of each. The scratch collection is deleted afterwards.

Usage: uv run poe check-hnsw   (after `poe index-corpus --docs all`)
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

from copilot.config import get_settings
from copilot.eval.splits import load_split
from copilot.ingest import index
from copilot.ingest.embed import FastEmbedDense

SCRATCH = "scratch_hnsw_check"
EF_VALUES = (8, 16, 32, 64, 128)
K = 10
OUT_DIR = Path("eval/results/indexing")


def copy_vectors(client: QdrantClient, source: str, dim: int) -> int:
    """Copy the dense vectors into a scratch collection that indexes every segment."""
    if client.collection_exists(SCRATCH):
        client.delete_collection(SCRATCH)
    client.create_collection(
        SCRATCH,
        vectors_config={
            index.DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)
        },
        hnsw_config=models.HnswConfigDiff(m=index.HNSW_M, ef_construct=index.HNSW_EF_CONSTRUCT),
        optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1),
    )
    offset: models.ExtendedPointId | None = None
    copied = 0
    while True:
        points, offset = client.scroll(
            source, limit=1000, offset=offset, with_payload=False, with_vectors=[index.DENSE]
        )
        batch = [
            models.PointStruct(id=point.id, vector={index.DENSE: point.vector[index.DENSE]})
            for point in points
            if isinstance(point.vector, dict)
        ]
        client.upsert(SCRATCH, points=batch, wait=True)
        copied += len(batch)
        if offset is None:
            return copied


def wait_for_index(client: QdrantClient, points: int, timeout_s: float = 600) -> float:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_s:
        info = client.get_collection(SCRATCH)
        if (
            info.status == models.CollectionStatus.GREEN
            and (info.indexed_vectors_count or 0) >= points
        ):
            return time.perf_counter() - started
        time.sleep(1)
    raise TimeoutError("The scratch collection did not finish indexing.")


def search(
    client: QdrantClient, vectors: list[list[float]], params: models.SearchParams
) -> tuple[list[list[str]], list[float]]:
    ids, latencies = [], []
    for vector in vectors:
        started = time.perf_counter()
        hits = client.query_points(
            SCRATCH, query=vector, using=index.DENSE, limit=K, search_params=params
        ).points
        latencies.append((time.perf_counter() - started) * 1000)
        ids.append([str(hit.id) for hit in hits])
    return ids, latencies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--collection", default="fb_tokens-480_bge-small")
    args = parser.parse_args(argv)

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url, timeout=120)
    dense = FastEmbedDense(cache_dir=settings.data_dir / "models")
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    vectors = [dense.embed_query(question.question).tolist() for question in questions]

    points = copy_vectors(client, args.collection, dense.dim)
    build_s = wait_for_index(client, points)
    exact, exact_ms = search(client, vectors, models.SearchParams(exact=True))
    rows = [{"search": "exact", "recall_at_10": 1.0, **_latency(exact_ms)}]
    for ef in EF_VALUES:
        found, ms = search(client, vectors, models.SearchParams(hnsw_ef=ef))
        recall = statistics.mean(
            len(set(hnsw) & set(truth)) / K for hnsw, truth in zip(found, exact, strict=True)
        )
        rows.append({"search": f"hnsw ef={ef}", "recall_at_10": round(recall, 4), **_latency(ms)})
    client.delete_collection(SCRATCH)

    result = {
        "collection": args.collection,
        "points": points,
        "queries": len(vectors),
        "hnsw": {"m": index.HNSW_M, "ef_construct": index.HNSW_EF_CONSTRUCT},
        "index_build_seconds": round(build_s, 1),
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / f"hnsw-{args.collection}"
    stem.with_suffix(".json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        f"# HNSW against exact search: {args.collection}",
        "",
        f"{points:,} dense vectors, {len(vectors)} dev questions, top {K}; "
        f"HNSW m = {index.HNSW_M}, ef_construct = {index.HNSW_EF_CONSTRUCT}; "
        f"graph built in {build_s:.0f} s. "
        "Latency is measured from the client, HTTP included.",
        "",
        "| Search | Recall@10 against exact | p50 ms | p95 ms |",
        "|---|---|---|---|",
        *[
            f"| {r['search']} | {r['recall_at_10']:.3f} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} |"
            for r in rows
        ],
        "",
    ]
    stem.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


def _latency(ms: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(float(np.percentile(ms, 50)), 2),
        "p95_ms": round(float(np.percentile(ms, 95)), 2),
    }


if __name__ == "__main__":
    raise SystemExit(main())
