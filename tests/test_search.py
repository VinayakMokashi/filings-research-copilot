"""Search modes, document filters, neighbours, reranking and page ranking."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import NDArray
from qdrant_client import QdrantClient

from copilot.eval.retrieval import PageRef
from copilot.ingest import index
from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import HashingDense, HashingSparse
from copilot.retrieval.rerank import OverlapReranker, rerank
from copilot.retrieval.search import Hit, Searcher, ranked_pages, with_neighbours

SPEC = index.IndexSpec("tokens-12", "hashing", 64)
DOCS = {
    "ACME_2022_10K": [
        "Acme revenue grew in 2022 on pump sales",
        "Capital expenditure was 1.2 billion dollars",
        "Litigation over the Delaware plant continues",
        "Dividends per share rose to 2.10",
    ],
    "BOLT_2022_10K": [
        "Bolt revenue fell as bolt prices dropped",
        "Capital expenditure on new mills was modest",
    ],
}


def _chunks() -> list[Chunk]:
    chunks = []
    for doc, texts in DOCS.items():
        for number, text in enumerate(texts):
            chunks.append(
                Chunk(
                    chunk_id=hashlib.sha256(f"{doc}|{number}".encode()).hexdigest(),
                    strategy="tokens-12",
                    doc_name=doc,
                    chunk_index=number,
                    text=text,
                    char_start=number * 100,
                    char_end=number * 100 + len(text),
                    pages=(number, number + 1),
                    section="7",
                    company=doc.split("_")[0].title(),
                    doc_period=2022,
                    doc_type="10k",
                    tokens=len(text.split()),
                )
            )
    return chunks


@pytest.fixture(scope="module")
def searcher() -> Searcher:
    client = QdrantClient(":memory:")
    index.ensure_collection(client, SPEC)

    def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
        return HashingDense().embed_documents([chunk.text for chunk in batch])

    index.index_chunks(client, SPEC.collection, _chunks(), embed, HashingSparse())
    return Searcher(client, SPEC.collection, HashingDense(), HashingSparse())


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid"])
def test_every_mode_finds_the_matching_chunk(searcher: Searcher, mode: str) -> None:
    hits = searcher.search("litigation Delaware plant", mode, limit=3)  # type: ignore[arg-type]

    assert hits[0].text == DOCS["ACME_2022_10K"][2]
    assert hits[0].pages == (2, 3)


def test_a_document_filter_keeps_other_filings_out(searcher: Searcher) -> None:
    everywhere = searcher.search("capital expenditure", "hybrid", limit=6)
    bolt_only = searcher.search(
        "capital expenditure", "hybrid", limit=6, doc_names=["BOLT_2022_10K"]
    )

    assert {hit.doc_name for hit in everywhere} == set(DOCS)
    assert {hit.doc_name for hit in bolt_only} == {"BOLT_2022_10K"}
    assert len(bolt_only) == 2


def test_neighbours_are_the_adjacent_chunks_of_the_same_document(searcher: Searcher) -> None:
    [hit] = searcher.search("litigation Delaware plant", "dense", limit=1)

    assert [n.chunk_index for n in searcher.neighbours(hit)] == [1, 3]
    expanded = with_neighbours(searcher, [hit], top=1)
    assert [h.chunk_index for h in expanded] == [2, 1, 3]


def _hit(index: int, text: str, pages: tuple[int, ...], doc: str = "ACME_2022_10K") -> Hit:
    return Hit(f"id{index}", 0.0, doc, index, pages, None, text)


def test_rerank_reorders_only_the_top_candidates() -> None:
    hits = [
        _hit(0, "dividends", (0,)),
        _hit(1, "capital expenditure rose", (1,)),
        _hit(2, "capital", (2,)),
    ]

    reranked = rerank(OverlapReranker(), "capital expenditure", hits, top=2)

    assert [h.point_id for h in reranked] == ["id1", "id0", "id2"]
    assert reranked[0].score == 2.0


def test_ranked_pages_follow_chunk_order_without_repeats() -> None:
    hits = [_hit(0, "a", (4, 3)), _hit(1, "b", (3,)), _hit(2, "c", (7, 8), doc="BOLT_2022_10K")]

    assert ranked_pages(hits) == [
        PageRef("ACME_2022_10K", 4),
        PageRef("ACME_2022_10K", 3),
        PageRef("BOLT_2022_10K", 7),
        PageRef("BOLT_2022_10K", 8),
    ]
    assert len(ranked_pages(hits, limit=3)) == 3


def test_weighted_fusion_can_favour_one_ranking(searcher: Searcher) -> None:
    from dataclasses import replace

    dense_heavy = replace(searcher, rrf_weights=(1.0, 0.0))
    dense_only = searcher.search("revenue pump prices", "dense", limit=3)

    hits = dense_heavy.search("revenue pump prices", "hybrid", limit=3)

    assert [h.point_id for h in hits] == [h.point_id for h in dense_only]
