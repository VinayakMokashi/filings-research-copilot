"""Embed one chunking strategy with one model into a Qdrant collection (ADR-0010).

Each document is one job: load its chunks (from `poe chunk-corpus`, or chunked here and
cached), embed the chunks the collection lacks, and upsert them with their BM25 vectors.
A rerun skips what is already stored, so an interrupted run just starts again. With
`--docs all` (the 84 filings behind FinanceBench's questions), documents behind dev
questions go first, so dev evaluation can start early; `--docs corpus` takes every parsed
filing.

Writes the collection fb_<strategy>_<model> (model `jina-small-late` with `--late`), a job
log and an index card under data/processed/indexes/.

`--model-dir` embeds with an encoder exported to ONNX instead (`copilot.ingest.embed.OnnxDense`;
the collection takes its `--key`). `--vectors` takes the passages' vectors from a file that a
GPU computed with that model (step 7.1's kernel writes vectors/<model>.npy beside
chunk_ids.json); a sample of them is embedded again here on the CPU first, and the run stops
if the two disagree. The card records the model's folder, so queries use the same model.

Usage: uv run poe index-corpus --strategy tokens-480 --model bge-small --docs all
       uv run poe index-corpus --strategy tokens-480 --model jina-small --late --docs dev
       uv run poe index-corpus --strategy page --docs all --key embedder-v1 \
           --model-dir data/models/embedder-v1/embedder \
           --vectors data/models/embedder-v1/vectors/embedder.npy
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
    OnnxDense,
)
from copilot.ingest.jobs import Job, JobResult, LocalRunner, select_documents
from copilot.ingest.late_chunking import JINA_REPO, WINDOW_OVERLAP, WINDOW_TOKENS, JinaEmbedder
from copilot.ingest.pdf import read_pages
from copilot.logs import configure_logging

STRATEGIES = ("page", "tokens-480", "tokens-256", "semantic")
MODELS = ("bge-small", "jina-small")
CHECK_TOLERANCE = 1e-3  # the largest difference allowed between stored and CPU vectors


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--strategy", choices=STRATEGIES, required=True)
    parser.add_argument("--model", choices=MODELS, default="bge-small")
    parser.add_argument("--late", action="store_true", help="late chunking (jina-small only)")
    parser.add_argument(
        "--docs",
        choices=("dev", "all", "corpus"),
        default="dev",
        help="dev filings, all question filings, or every parsed filing",
    )
    parser.add_argument("--limit", type=int, help="index only the first N documents")
    parser.add_argument("--rechunk", action="store_true", help="ignore cached chunk files")
    parser.add_argument("--model-dir", type=Path, help="an ONNX encoder's folder (OnnxDense)")
    parser.add_argument("--key", help="with --model-dir: the model's name in the collection's")
    parser.add_argument("--model-name", help="with --model-dir: what the card calls the model")
    parser.add_argument("--vectors", type=Path, help="with --model-dir: precomputed vectors")
    parser.add_argument("--check", type=int, default=16, help="chunks to check --vectors on")
    args = parser.parse_args(argv)
    if args.late and args.model != "jina-small":
        parser.error("--late needs --model jina-small")
    if (args.key or args.model_name or args.vectors) and not args.model_dir:
        parser.error("--key, --model-name and --vectors need --model-dir")

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
    questions = {question.doc_name for question in fb.load_questions(fb_root)}
    names = select_documents(parsed, dev, questions, args.docs)[: args.limit]

    model_dir: Path | None = None
    if args.model_dir:
        try:
            model_dir = args.model_dir.resolve().relative_to(settings.data_dir.resolve())
        except ValueError:
            parser.error("--model-dir must be inside the data directory")
    jina = JinaEmbedder() if args.model == "jina-small" and not args.model_dir else None
    dense: DenseEmbedder
    if args.model_dir:
        dense = OnnxDense.load(args.model_dir, key=args.key)
    else:
        dense = jina if jina is not None else FastEmbedDense(cache_dir=cache_dir)
    stored = index.StoredVectors(args.vectors) if args.vectors else None
    sparse = FastEmbedBM25(cache_dir=cache_dir)
    chunker = make_chunker(args.strategy, None if jina is not None else dense, cache_dir)
    model_key = f"{dense.key}-late" if args.late else dense.key
    spec = index.IndexSpec(args.strategy, model_key, dense.dim)

    client = QdrantClient(url=settings.qdrant_url, timeout=120)

    def load_doc(name: str) -> AssembledDocument:
        return assemble(read_pages(pages_path(pages_dir, name)), documents[name])

    def chunks_for(name: str) -> list[Chunk]:
        path = chunks_dir / f"{name}.jsonl"
        if path.exists() and not args.rechunk:
            return read_chunks(path)
        chunks = chunker.chunk(load_doc(name))
        write_chunks(chunks, path)
        return chunks

    check: dict[str, object] | None = None
    if stored is not None:
        # One chunk from each of a spread of the documents, embedded again on the CPU.
        sample = [chunks_for(name)[0] for name in names[:: max(1, len(names) // args.check)]]
        difference = stored.check(dense, sample[: args.check])
        check = {"chunks": len(sample[: args.check]), "max_abs_diff": difference}
        print(f"Stored vectors against the CPU on {check['chunks']} chunks: {difference:.2e}")
        if difference > CHECK_TOLERANCE:
            print(f"They differ by more than {CHECK_TOLERANCE}; nothing indexed.")
            return 1
    index.ensure_collection(client, spec)

    def handle(job: Job) -> JobResult:
        chunks = chunks_for(job.doc_name)
        if args.late and jina is not None:
            text = load_doc(job.doc_name).text

            def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
                return jina.embed_late(text, [(c.char_start, c.char_end) for c in batch])

            batch_size = 256  # whole windows per call; each call re-runs one shared window
        elif stored is not None:
            vectors = stored

            def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
                return vectors(batch)

            batch_size = 256
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

    if model_dir:
        model_name = args.model_name or model_key
    else:
        model_name = JINA_REPO if jina is not None else BGE_MODEL
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
            "model": model_name,
            "dim": dense.dim,
            "distance": "cosine",
            "query_model": "onnx" if model_dir else dense.key,
            "query_prefix": "" if jina is not None else BGE_QUERY_INSTRUCTION,
            "late_chunking": (
                {"window_tokens": WINDOW_TOKENS, "overlap_tokens": WINDOW_OVERLAP}
                if args.late
                else None
            ),
        }
        | ({"model_dir": model_dir.as_posix()} if model_dir else {})
        | ({"vectors": {"file": args.vectors.as_posix(), "check": check}} if check else {}),
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
