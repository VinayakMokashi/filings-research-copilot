"""The Qdrant index: one collection per chunking strategy and embedding model (ADR-0010).

Each point holds a dense vector (`dense`), a BM25 sparse vector (`bm25`, with IDF applied by
Qdrant) and the chunk as payload. Point ids come from the chunk's content hash, so upserting
a chunk twice changes nothing, and an interrupted run resumes by skipping ids already
present. Payload indexes on document, company, form, fiscal period and section keep filtered
search fast. HNSW uses Qdrant's defaults (m = 16, ef_construct = 100), recorded here so a
change is deliberate.

Every collection has an index card (`read_card`) that records what it holds and which model
made its vectors, so a search embeds its queries with the same model. `StoredVectors` lets a
collection take vectors computed elsewhere, such as on a GPU for a fine-tuned model.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient, models

from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import DenseEmbedder, SparseEmbedder, SparseVector

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


def card_path(data_dir: Path, collection: str) -> Path:
    """Where a collection's index card is: what it holds, and which models made its vectors."""
    return data_dir / "processed" / "indexes" / f"{collection}.json"


def read_card(data_dir: Path, collection: str) -> dict[str, Any] | None:
    """A collection's index card, or None if it has none."""
    path = card_path(data_dir, collection)
    if not path.exists():
        return None
    card: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return card


class StoredVectors:
    """Passage vectors computed elsewhere (on a GPU, say), looked up by chunk id.

    The file is a NumPy array with one row a chunk; chunk_ids.json beside it names each
    row's chunk. `check` compares a sample with an embedder's own vectors.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.vectors = np.load(path)
        ids = json.loads((path.parent / "chunk_ids.json").read_text(encoding="utf-8"))
        if len(ids) != len(self.vectors):
            raise ValueError(f"{path} has {len(self.vectors)} rows for {len(ids)} chunk ids.")
        self.row = {chunk_id: row for row, chunk_id in enumerate(ids)}

    def __call__(self, batch: Sequence[Chunk]) -> NDArray[np.float32]:
        missing = [chunk.chunk_id for chunk in batch if chunk.chunk_id not in self.row]
        if missing:
            raise KeyError(f"{self.path} has no vectors for {len(missing)} chunks.")
        rows = [self.row[chunk.chunk_id] for chunk in batch]
        return np.asarray(self.vectors[rows], dtype=np.float32)

    def check(self, dense: DenseEmbedder, chunks: Sequence[Chunk]) -> float:
        """The largest difference between the stored vectors and `dense`'s, on `chunks`."""
        expected = dense.embed_documents([chunk.text for chunk in chunks])
        return float(np.max(np.abs(self(chunks) - expected)))
