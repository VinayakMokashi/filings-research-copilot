"""Search one collection: dense, BM25 or hybrid, optionally within given documents (step 2.4).

Hybrid search asks Qdrant for the top candidates by the dense vector and by BM25 in one
call, and fuses the two rankings with reciprocal rank fusion (RRF): a chunk scores the sum
of w / (k + rank) over the lists it appears in, where w is the list's weight (1 unless set).
k = 60 follows Cormack et al. (2009); Qdrant's own default, k = 2, lets the first few ranks
of either list dominate.

Retrieval is scored by page, so `ranked_pages` turns ranked chunks into ranked pages: each
chunk's pages in order of how much of the chunk they hold, first appearance wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from qdrant_client import QdrantClient, models

from copilot.eval.retrieval import PageRef
from copilot.ingest.embed import DenseEmbedder, SparseEmbedder
from copilot.ingest.index import DENSE, SPARSE

Mode = Literal["dense", "bm25", "hybrid"]
MODES: tuple[Mode, ...] = ("dense", "bm25", "hybrid")
RRF_K = 60
CANDIDATES = 50  # per ranking, before fusion


@dataclass(frozen=True, slots=True)
class Hit:
    point_id: str
    score: float
    doc_name: str
    chunk_index: int
    pages: tuple[int, ...]
    section: str | None
    text: str

    @classmethod
    def from_point(cls, point: models.ScoredPoint | models.Record) -> Hit:
        payload: dict[str, Any] = point.payload or {}
        return cls(
            point_id=str(point.id),
            score=float(getattr(point, "score", 0.0) or 0.0),
            doc_name=payload["doc_name"],
            chunk_index=int(payload["chunk_index"]),
            pages=tuple(payload["pages"]),
            section=payload.get("section"),
            text=payload["text"],
        )


def document_filter(doc_names: Sequence[str] | None) -> models.Filter | None:
    if doc_names is None:
        return None
    return models.Filter(
        must=[models.FieldCondition(key="doc_name", match=models.MatchAny(any=list(doc_names)))]
    )


@dataclass(frozen=True, slots=True)
class Searcher:
    """Searches one collection with the models it was built with."""

    client: QdrantClient
    collection: str
    dense: DenseEmbedder
    sparse: SparseEmbedder
    candidates: int = CANDIDATES
    rrf_k: int = RRF_K
    rrf_weights: tuple[float, float] | None = None  # (dense, BM25); None weighs them equally

    def search(
        self,
        query: str,
        mode: Mode = "hybrid",
        limit: int = 20,
        doc_names: Sequence[str] | None = None,
    ) -> list[Hit]:
        """The top `limit` chunks for `query`, searching only `doc_names` if given."""
        where = document_filter(doc_names)
        if mode == "dense":
            response = self.client.query_points(
                self.collection,
                query=self.dense.embed_query(query).tolist(),
                using=DENSE,
                query_filter=where,
                limit=limit,
                with_payload=True,
            )
        elif mode == "bm25":
            response = self.client.query_points(
                self.collection,
                query=self._sparse_query(query),
                using=SPARSE,
                query_filter=where,
                limit=limit,
                with_payload=True,
            )
        else:
            depth = max(limit, self.candidates)
            response = self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(
                        query=self.dense.embed_query(query).tolist(),
                        using=DENSE,
                        filter=where,
                        limit=depth,
                    ),
                    models.Prefetch(
                        query=self._sparse_query(query), using=SPARSE, filter=where, limit=depth
                    ),
                ],
                query=models.RrfQuery(
                    rrf=models.Rrf(
                        k=self.rrf_k,
                        weights=list(self.rrf_weights) if self.rrf_weights else None,
                    )
                ),
                query_filter=where,
                limit=limit,
                with_payload=True,
            )
        return [Hit.from_point(point) for point in response.points]

    def neighbours(self, hit: Hit, window: int = 1) -> list[Hit]:
        """The chunks up to `window` places before and after `hit` in its document."""
        wanted = [
            index
            for index in range(hit.chunk_index - window, hit.chunk_index + window + 1)
            if index >= 0 and index != hit.chunk_index
        ]
        points, _ = self.client.scroll(
            self.collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_name", match=models.MatchValue(value=hit.doc_name)
                    ),
                    models.FieldCondition(key="chunk_index", match=models.MatchAny(any=wanted)),
                ]
            ),
            limit=len(wanted),
            with_payload=True,
        )
        return sorted((Hit.from_point(point) for point in points), key=lambda h: h.chunk_index)

    def _sparse_query(self, query: str) -> models.SparseVector:
        vector = self.sparse.embed_query(query)
        return models.SparseVector(indices=vector.indices, values=vector.values)


def with_neighbours(
    searcher: Searcher, hits: Sequence[Hit], top: int = 5, window: int = 1
) -> list[Hit]:
    """Each of the top `top` hits followed by its neighbouring chunks, then the rest."""
    expanded: list[Hit] = []
    seen: set[str] = set()
    for rank, hit in enumerate(hits):
        group = [hit, *searcher.neighbours(hit, window)] if rank < top else [hit]
        for member in group:
            if member.point_id not in seen:
                seen.add(member.point_id)
                expanded.append(member)
    return expanded


def ranked_pages(hits: Sequence[Hit], limit: int = 20) -> list[PageRef]:
    """Pages in the order their chunks rank, each chunk's pages most-covered first."""
    pages: list[PageRef] = []
    seen: set[PageRef] = set()
    for hit in hits:
        for page in hit.pages:
            ref = PageRef(hit.doc_name, page)
            if ref not in seen:
                seen.add(ref)
                pages.append(ref)
                if len(pages) == limit:
                    return pages
    return pages
