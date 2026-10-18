"""Search one collection: dense, BM25 or hybrid, optionally within given documents (step 2.4).

Hybrid search takes the top candidates by the dense vector and by BM25 and fuses the two
rankings with reciprocal rank fusion (RRF): a chunk scores the sum of w / (k + rank) over
the rankings it appears in, with rank counted from 1 and w the ranking's weight (1 unless
set). k = 60 follows Cormack et al. (2009).

The fusion runs here rather than in Qdrant, for two measured reasons. Qdrant ranks tied
scores in no fixed order, and RRF turns those arbitrary ranks into different fused scores,
so the same query could return a different order on every call. And Qdrant's RRF weights
rescale ranks instead of multiplying scores (see the hybrid search guide). Each ranking is
put in a fixed order first: by score, then by point id.

Retrieval is scored by page, so `ranked_pages` turns ranked chunks into ranked pages: each
chunk's pages in order of how much of the chunk they hold, first appearance wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from qdrant_client import QdrantClient, models

from copilot.eval.retrieval import PageRef
from copilot.ingest.embed import DenseEmbedder, SparseEmbedder
from copilot.ingest.index import DENSE, SPARSE

Mode = Literal["dense", "bm25", "hybrid"]
MODES: tuple[Mode, ...] = ("dense", "bm25", "hybrid")
RRF_K = 60
CANDIDATES = 50  # per ranking, before fusion
TIE_MARGIN = 20  # extra results fetched, so ties at the cut-off are settled the same way each time


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
            return self._ranking(self.dense.embed_query(query).tolist(), DENSE, where, limit)
        if mode == "bm25":
            return self._ranking(self._sparse_query(query), SPARSE, where, limit)
        depth = max(limit, self.candidates)
        rankings = [
            self._ranking(self.dense.embed_query(query).tolist(), DENSE, where, depth),
            self._ranking(self._sparse_query(query), SPARSE, where, depth),
        ]
        return reciprocal_rank_fusion(rankings, self.rrf_k, self.rrf_weights)[:limit]

    def _ranking(
        self,
        query: list[float] | models.SparseVector,
        using: str,
        where: models.Filter | None,
        limit: int,
    ) -> list[Hit]:
        """One vector's top `limit` hits, ties broken by point id."""
        response = self.client.query_points(
            self.collection,
            query=query,
            using=using,
            query_filter=where,
            limit=limit + TIE_MARGIN,
            with_payload=True,
        )
        hits = [Hit.from_point(point) for point in response.points]
        return sorted(hits, key=lambda hit: (-round(hit.score, 9), hit.point_id))[:limit]

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


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hit]], k: int = RRF_K, weights: Sequence[float] | None = None
) -> list[Hit]:
    """Hits from all rankings by the sum of weight / (k + rank), ties broken by point id."""
    scores: dict[str, float] = {}
    first_seen: dict[str, Hit] = {}
    for ranking, weight in zip(rankings, weights or [1.0] * len(rankings), strict=True):
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.point_id] = scores.get(hit.point_id, 0.0) + weight / (k + rank)
            first_seen.setdefault(hit.point_id, hit)
    order = sorted(scores, key=lambda point_id: (-round(scores[point_id], 12), point_id))
    return [replace(first_seen[point_id], score=scores[point_id]) for point_id in order]


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
