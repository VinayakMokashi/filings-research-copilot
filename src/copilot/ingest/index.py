"""The Qdrant index: one collection per chunking strategy and embedding model (ADR-0010).

Each point holds a dense vector (`dense`), a BM25 sparse vector (`bm25`, with IDF applied by
Qdrant) and the chunk as payload. Point ids come from the chunk's content hash, so upserting
a chunk twice changes nothing, and an interrupted run resumes by skipping ids already
present. Payload indexes on document, company, form, fiscal period and section keep filtered
search fast. HNSW uses Qdrant's defaults (m = 16, ef_construct = 100), recorded here so a
change is deliberate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import islice
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient, models

from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import SparseEmbedder, SparseVector

DENSE = "dense"
SPARSE = "bm25"
HNSW_M = 16
HNSW_EF_CONSTRUCT = 100
PAYLOAD_INDEXES: dict[str, models.PayloadSchemaType] = {
    "doc_name": models.PayloadSchemaType.KEYWORD,
    "company": models.PayloadSchemaType.KEYWORD,
    "doc_type": models.PayloadSchemaType.KEYWORD,
    "section": models.PayloadSchemaType.KEYWORD,
    "doc_period": models.PayloadSchemaType.INTEGER,
}


@dataclass(frozen=True, slots=True)
class IndexSpec:
    strategy: str
    model: str
    dim: int

    @property
    def collection(self) -> str:
        return f"fb_{self.strategy}_{self.model}"


def ensure_collection(client: QdrantClient, spec: IndexSpec) -> bool:
    """Create the collection and its payload indexes if missing; True if it was created."""
    if client.collection_exists(spec.collection):
        return False
    client.create_collection(
        collection_name=spec.collection,
        vectors_config={DENSE: models.VectorParams(size=spec.dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        hnsw_config=models.HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT),
    )
    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(spec.collection, field_name=field, field_schema=schema)
    return True


def _batches(items: Sequence[Any], size: int) -> Iterator[list[Any]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def missing(client: QdrantClient, collection: str, chunks: Sequence[Chunk]) -> list[Chunk]:
    """The chunks whose point ids aren't in the collection yet."""
    present: set[str] = set()
    for batch in _batches([chunk.point_id for chunk in chunks], 512):
        found = client.retrieve(collection, ids=batch, with_payload=False, with_vectors=False)
        present |= {str(point.id) for point in found}
    return [chunk for chunk in chunks if chunk.point_id not in present]


def payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "strategy": chunk.strategy,
        "doc_name": chunk.doc_name,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "pages": list(chunk.pages),
        "section": chunk.section,
        "company": chunk.company,
        "doc_period": chunk.doc_period,
        "doc_type": chunk.doc_type,
        "tokens": chunk.tokens,
    }


def upsert(
    client: QdrantClient,
    collection: str,
    chunks: Sequence[Chunk],
    dense: NDArray[np.float32],
    sparse: Sequence[SparseVector],
    batch_size: int = 256,
) -> None:
    points = [
        models.PointStruct(
            id=chunk.point_id,
            vector={
                DENSE: dense_vector.tolist(),
                SPARSE: models.SparseVector(
                    indices=sparse_vector.indices, values=sparse_vector.values
                ),
            },
            payload=payload(chunk),
        )
        for chunk, dense_vector, sparse_vector in zip(chunks, dense, sparse, strict=True)
    ]
    for batch in _batches(points, batch_size):
        client.upsert(collection, points=batch, wait=True)


EmbedChunks = Callable[[Sequence[Chunk]], NDArray[np.float32]]


def index_chunks(
    client: QdrantClient,
    collection: str,
    chunks: Sequence[Chunk],
    embed: EmbedChunks,
    sparse: SparseEmbedder,
    batch_size: int = 64,
) -> int:
    """Embed and store the chunks the collection lacks, a batch at a time; returns how many."""
    todo = missing(client, collection, chunks)
    for batch in _batches(todo, batch_size):
        vectors = embed(batch)
        upsert(client, collection, batch, vectors, sparse.embed_documents([c.text for c in batch]))
    return len(todo)


def count(client: QdrantClient, collection: str) -> int:
    return int(client.count(collection, exact=True).count)
