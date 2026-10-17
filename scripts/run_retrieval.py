"""Run one retrieval configuration over FinanceBench questions and score it (steps 2.4, 2.5).

Writes a run to eval/results/retrieval/<run>/<split>/, as `poe eval-retrieval` does, with
the pages each question retrieved, its latency and the configuration. Two settings:
`oracle` searches only the question's own document (FinanceBench's single-document
setting); `corpus` searches every document in the collection.

Usage:
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode dense
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode hybrid --rerank minilm-l6
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode hybrid --setting corpus
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient

from copilot.config import get_settings
from copilot.eval import retrieval
from copilot.eval.report import (
    RESULTS_DIR,
    RunSummary,
    render_markdown,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import HeldOutError, load_split
from copilot.ingest.embed import DenseEmbedder, FastEmbedBM25, FastEmbedDense
from copilot.ingest.late_chunking import JinaEmbedder
from copilot.logs import configure_logging
from copilot.retrieval.rerank import RERANKERS, FastEmbedReranker, rerank
from copilot.retrieval.search import MODES, Searcher, ranked_pages, with_neighbours

FETCH = 60  # chunks per question: enough for 20 distinct pages with small chunks
PAGES = max(retrieval.KS)


def query_embedder(card: dict[str, Any], cache_dir: Path) -> DenseEmbedder:
    """The embedder a collection's queries need, as its index card records."""
    model = card["dense"]["query_model"]
    if model == "bge-small":
        return FastEmbedDense(cache_dir=cache_dir)
    if model == "jina-small":
        return JinaEmbedder()
    raise ValueError(f"No query embedder for {model!r}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--collection", required=True, help="for example fb_tokens-480_bge-small")
    parser.add_argument("--mode", choices=MODES, default="hybrid")
    parser.add_argument(
        "--rrf-weights", help="hybrid only: dense and BM25 weights, for example 2,1"
    )
    parser.add_argument("--rerank", choices=sorted(RERANKERS), help="cross-encoder to rerank with")
    parser.add_argument("--rerank-top", type=int, default=30, help="candidates the reranker sees")
    parser.add_argument("--neighbours", type=int, default=0, help="chunks added on each side")
    parser.add_argument("--neighbours-top", type=int, default=5, help="hits that get neighbours")
    parser.add_argument("--setting", choices=("oracle", "corpus"), default="oracle")
    parser.add_argument("--run", help="run name (derived from the configuration by default)")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "raw" / "financebench"
    try:
        questions = load_split(args.split, root, allow_test=args.allow_test)
    except HeldOutError:
        print("The test split is held out (ADR-0006). Add --allow-test only for a milestone.")
        return 2

    card_path = settings.data_dir / "processed" / "indexes" / f"{args.collection}.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    cache_dir = settings.data_dir / "models"
    weights = None
    if args.rrf_weights:
        dense_weight, sparse_weight = (float(part) for part in args.rrf_weights.split(","))
        weights = (dense_weight, sparse_weight)
    searcher = Searcher(
        QdrantClient(url=settings.qdrant_url, timeout=120),
        args.collection,
        query_embedder(card, cache_dir),
        FastEmbedBM25(cache_dir=cache_dir),
        rrf_weights=weights,
    )
    reranker = FastEmbedReranker(args.rerank, cache_dir=cache_dir) if args.rerank else None

    predictions: dict[str, list[retrieval.PageRef]] = {}
    latency: dict[str, float] = {}
    for question in questions:
        started = time.perf_counter()
        documents = [question.doc_name] if args.setting == "oracle" else None
        hits = searcher.search(question.question, args.mode, FETCH, documents)
        if reranker is not None:
            hits = rerank(reranker, question.question, hits, args.rerank_top)
        if args.neighbours:
            hits = with_neighbours(searcher, hits, args.neighbours_top, args.neighbours)
        predictions[question.id] = ranked_pages(hits, PAGES)
        latency[question.id] = (time.perf_counter() - started) * 1000

    rows = retrieval.score(questions, predictions)
    for row in rows:
        row["latency_ms"] = round(latency[row["id"]], 1)
    names = retrieval.metric_names()
    times = list(latency.values())
    system: dict[str, Any] = {
        "collection": args.collection,
        "strategy": card["strategy"],
        "dense_model": card["dense"]["model"],
        "late_chunking": card["dense"]["late_chunking"] is not None,
        "index_documents": card["documents"],
        "mode": args.mode,
        "setting": args.setting,
        "fetched_chunks": FETCH,
        "latency_ms": {
            "p50": round(float(np.percentile(times, 50)), 1),
            "p95": round(float(np.percentile(times, 95)), 1),
            "mean": round(statistics.mean(times), 1),
        },
    }
    if args.mode == "hybrid":
        system |= {"rrf_k": searcher.rrf_k, "candidates_per_ranking": searcher.candidates}
        if weights:
            system |= {"rrf_weights": {"dense": weights[0], "bm25": weights[1]}}
    if reranker is not None:
        system |= {"reranker": reranker.model_id, "rerank_top": args.rerank_top}
    if args.neighbours:
        system |= {"neighbours": args.neighbours, "neighbours_top": args.neighbours_top}

    run = args.run or "-".join(
        part
        for part in (
            args.collection.removeprefix("fb_"),
            args.mode,
            f"w{args.rrf_weights.replace(',', '-')}" if args.rrf_weights else "",
            f"rerank-{args.rerank}" if args.rerank else "",
            f"nb{args.neighbours}" if args.neighbours else "",
            args.setting,
        )
        if part
    )
    summary = RunSummary(
        suite="retrieval",
        run=run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system=system,
        metrics=summarise(rows, names),
        by={"question_type": summarise_by(rows, names, "question_type")},
    )
    directory = args.results_dir / "retrieval" / run / args.split
    write_run(directory, summary, rows)
    print(render_markdown(summary))
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
