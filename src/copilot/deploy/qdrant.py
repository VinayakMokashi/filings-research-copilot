"""Copy the doc agent's collection to Qdrant Cloud, and snapshot it (ADR-0031).

The collection is copied point by point: its named dense and sparse vectors, its
payloads and its payload indexes, recreated from the source's own configuration. A
copy survives a difference between the local and the cloud's Qdrant versions, which a
snapshot restore might not. A target that already holds every point is left alone.

Qdrant Cloud's free cluster is suspended after a week without use and deleted after
four, so a snapshot of the copied collection is kept in Cloud Storage to restore from.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import httpx
from qdrant_client import QdrantClient, models


def copy_collection(
    source: QdrantClient,
    target: QdrantClient,
    name: str,
    *,
    batch: int = 256,
    progress: Callable[[int], None] | None = None,
) -> int:
    """Copy collection `name` from `source` to `target`; returns the points copied.

    Creates the collection with the source's vector settings and payload indexes when
    it doesn't exist. Upserts are idempotent (the points keep their IDs), so an
    interrupted copy can simply run again.
    """
    info = source.get_collection(name)
    total = source.count(name, exact=True).count
    if target.collection_exists(name):
        if target.count(name, exact=True).count == total:
            return 0
    else:
        params = info.config.params
        target.create_collection(
            name,
            vectors_config=params.vectors,
            sparse_vectors_config=params.sparse_vectors,
            on_disk_payload=True,
        )
        for field, schema in (info.payload_schema or {}).items():
            if schema.data_type is not None:
                target.create_payload_index(name, field, field_schema=schema.data_type)

    copied = 0
    offset: models.ExtendedPointId | None = None
    while True:
        records, offset = source.scroll(
            name, limit=batch, offset=offset, with_payload=True, with_vectors=True
        )
        if records:
            target.upsert(
                name,
                points=[
                    models.PointStruct(
                        id=r.id, vector=cast(models.VectorStruct, r.vector or {}), payload=r.payload
                    )
                    for r in records
                ],
            )
            copied += len(records)
            if progress is not None:
                progress(copied)
        if offset is None:
            break
    return copied


def download_snapshot(url: str, api_key: str, name: str, out: Path) -> Path:
    """Take a snapshot of collection `name` on the cluster at `url` and save it to `out`."""
    headers = {"api-key": api_key}
    with httpx.Client(base_url=url, headers=headers, timeout=600.0) as http:
        made = http.post(f"/collections/{name}/snapshots", params={"wait": "true"})
        made.raise_for_status()
        snapshot = made.json()["result"]["name"]
        out.parent.mkdir(parents=True, exist_ok=True)
        with http.stream("GET", f"/collections/{name}/snapshots/{snapshot}") as response:
            response.raise_for_status()
            with out.open("wb") as f:
                for chunk in response.iter_bytes(1 << 20):
                    f.write(chunk)
        # The cluster has 4 GB of disk; the copy in Cloud Storage is the one kept.
        http.delete(f"/collections/{name}/snapshots/{snapshot}").raise_for_status()
    return out
