"""Embed one chunking strategy with one model into a Qdrant collection (ADR-0010).

Each document is one job: load its chunks (from `poe chunk-corpus`, or chunked here and
cached), embed the chunks the collection lacks, and upsert them with their BM25 vectors.
A rerun skips what is already stored, so an interrupted run just starts again. With
`--docs all`, documents behind dev questions go first, so dev evaluation can start early.

Writes the collection fb_<strategy>_<model> (model `jina-small-late` with `--late`), a job
log and an index card under data/processed/indexes/.

Usage: uv run poe index-corpus --strategy tokens-480 --model bge-small --docs all
       uv run poe index-corpus --strategy tokens-480 --model jina-small --late --docs dev
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.eval.splits import load_split
from copilot.ingest import index
from copilot.ingest.chunking import (
    AssembledDocument,
    Chunk,
    Chunker,
    PageChunker,
    SemanticChunker,
    TokenChunker,
    assemble,
    bge_token_offsets,
    read_chunks,
    write_chunks,
)
from copilot.ingest.corpus import pages_path
from copilot.ingest.embed import (
    BGE_MODEL,
    BGE_QUERY_INSTRUCTION,
    SPARSE_MODEL,
    DenseEmbedder,
    FastEmbedBM25,
    FastEmbedDense,
)
from copilot.ingest.jobs import Job, JobResult, LocalRunner
from copilot.ingest.late_chunking import JINA_REPO, WINDOW_OVERLAP, WINDOW_TOKENS, JinaEmbedder
from copilot.ingest.pdf import read_pages
from copilot.logs import configure_logging

STRATEGIES = ("page", "tokens-480", "tokens-256", "semantic")
MODELS = ("bge-small", "jina-small")


def make_chunker(strategy: str, units: DenseEmbedder | None, cache_dir: Path) -> Chunker:
    """The chunker for a strategy; semantic chunking embeds its units with bge-small."""
    offsets = bge_token_offsets()
    if strategy == "page":
        return PageChunker(offsets, max_tokens=480)
    if strategy == "tokens-480":
        return TokenChunker(offsets, max_tokens=480, overlap=64)
    if strategy == "tokens-256":
        return TokenChunker(offsets, max_tokens=256, overlap=32)
    if strategy == "semantic":
        embedder = units if units is not None else FastEmbedDense(cache_dir=cache_dir)
        return SemanticChunker(offsets, embedder.embed_documents)
    raise ValueError(f"Unknown strategy {strategy!r}; choose from {', '.join(STRATEGIES)}.")


def ordered_docs(documents: Sequence[str], dev: set[str], which: str) -> list[str]:
    """Dev documents first (sorted), then, for `all`, the rest (sorted)."""
    first = sorted(name for name in documents if name in dev)
    rest = sorted(name for name in documents if name not in dev)
    return first if which == "dev" else first + rest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--strategy", choices=STRATEGIES, required=True)
    parser.add_argument("--model", choices=MODELS, default="bge-small")
    parser.add_argument("--late", action="store_true", help="late chunking (jina-small only)")
    parser.add_argument("--docs", choices=("dev", "all"), default="dev")
    parser.add_argument("--limit", type=int, help="index only the first N documents")
    parser.add_argument("--rechunk", action="store_true", help="ignore cached chunk files")
    args = parser.parse_args(argv)
    if args.late and args.model != "jina-small":
        parser.error("--late needs --model jina-small")

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    fb_root = settings.data_dir / "raw" / "financebench"
    pages_dir = settings.data_dir / "processed" / "pages"
    chunks_dir = settings.data_dir / "processed" / "chunks" / args.strategy
    out_dir = settings.data_dir / "processed" / "indexes"
    cache_dir = settings.data_dir / "models"

    documents = fb.load_documents(fb_root)
    parsed = [path.stem for path in pages_dir.glob("*.jsonl") if path.stem in documents]
    dev = {question.doc_name for question in load_split("dev", fb_root)}
    names = ordered_docs(parsed, dev, args.docs)[: args.limit]

    jina = JinaEmbedder() if args.model == "jina-small" else None
    dense: DenseEmbedder = jina if jina is not None else FastEmbedDense(cache_dir=cache_dir)
    sparse = FastEmbedBM25(cache_dir=cache_dir)
    chunker = make_chunker(args.strategy, None if jina is not None else dense, cache_dir)
    model_key = f"{dense.key}-late" if args.late else dense.key
    spec = index.IndexSpec(args.strategy, model_key, dense.dim)

    client = QdrantClient(url=settings.qdrant_url, timeout=120)
    index.ensure_collection(client, spec)

    def load_doc(name: str) -> AssembledDocument:
        return assemble(read_pages(pages_path(pages_dir, name)), documents[name])

    def chunks_for(name: str) -> list[Chunk]:
        path = chunks_dir / f"{name}.jsonl"
        if path.exists() and not args.rechunk:
            return read_chunks(path)
        chunks = chunker.chunk(load_doc(name))
        write_chunks(chunks, path)
        return chunks

    def handle(job: Job) -> JobResult:
        chunks = chunks_for(job.doc_name)
        if args.late and jina is not None:
            text = load_doc(job.doc_name).text

            def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
                return jina.embed_late(text, [(c.char_start, c.char_end) for c in batch])

            batch_size = 256  # whole windows per call; each call re-runs one shared window
        else:

            def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
                return dense.embed_documents([c.text for c in batch])

            batch_size = 64
        added = index.index_chunks(client, spec.collection, chunks, embed, sparse, batch_size)
        return JobResult(job.doc_name, chunks=len(chunks), added=added)

    started = time.perf_counter()
    log_path = out_dir / f"{spec.collection}.log.jsonl"
    results = LocalRunner(log_path).run([Job(name) for name in names], handle)
    elapsed = time.perf_counter() - started

    failed = [r.doc_name for r in results if r.error]
    chunks_total = sum(r.chunks for r in results)
    points = index.count(client, spec.collection)
    card = {
        "collection": spec.collection,
        "strategy": args.strategy,
        "doc_set": args.docs,
        "documents": len(results) - len(failed),
        "failed": failed,
        "chunks": chunks_total,
        "points": points,
        "complete": not failed and points >= chunks_total,
        "dense": {
            "key": model_key,
            "model": JINA_REPO if jina is not None else BGE_MODEL,
            "dim": dense.dim,
            "distance": "cosine",
            "query_model": dense.key,
            "query_prefix": "" if jina is not None else BGE_QUERY_INSTRUCTION,
            "late_chunking": (
                {"window_tokens": WINDOW_TOKENS, "overlap_tokens": WINDOW_OVERLAP}
                if args.late
                else None
            ),
        },
        "sparse": {"model": SPARSE_MODEL, "modifier": "idf"},
        "hnsw": {"m": index.HNSW_M, "ef_construct": index.HNSW_EF_CONSTRUCT},
        "payload_indexes": sorted(index.PAYLOAD_INDEXES),
        "seconds": round(elapsed),
        "added": sum(r.added for r in results),
        "updated": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    card_path: Path = out_dir / f"{spec.collection}.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"{spec.collection}: {card['documents']} documents, {chunks_total:,} chunks, "
        f"{points:,} points, {card['added']:,} added in {elapsed:.0f} s; failed: {failed or 'none'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
