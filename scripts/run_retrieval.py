"""Run one retrieval configuration over FinanceBench questions and score it (steps 2.4, 2.5).

Writes a run to eval/results/retrieval/<run>/<split>/, as `poe eval-retrieval` does, with
the pages each question retrieved, its latency and the configuration. Three settings:
`oracle` searches only the question's own document (FinanceBench's single-document
setting); `corpus` searches every document in the collection; `understood` searches the
filings that query understanding resolves from the question's company, period and form,
or everything when it finds no company.

Usage:
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode dense
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode hybrid --rerank minilm-l6
  uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode hybrid --setting corpus
  uv run poe run-retrieval --collection fb_page_bge-small --mode dense --setting understood
  uv run poe run-retrieval --collection fb_page_bge-small --mode dense --setting understood \
      --rewrite multi    # also search model-written rewrites

Rewrites (`multi`, `hyde`, `decompose`, or `all`) call the fast model through a disk cache
(data/cache/llm.jsonl), so a rerun spends no quota; uncached calls are paced for the free
tier.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient

from copilot.config import get_settings
from copilot.eval import financebench as fb
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
from copilot.ingest.universe import read_companies
from copilot.llm import LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging
from copilot.retrieval.query import CompanyMatcher, filings_from, resolve, understand
from copilot.retrieval.rerank import RERANKERS, FastEmbedReranker, rerank
from copilot.retrieval.rewrite import PROMPT_VERSION as REWRITE_PROMPT_VERSION
from copilot.retrieval.rewrite import REWRITES, Rewrite, Search, expand
from copilot.retrieval.search import (
    MODES,
    RRF_K,
    Searcher,
    ranked_pages,
    reciprocal_rank_fusion,
    with_neighbours,
)

FETCH = 60  # chunks per question: enough for 20 distinct pages with small chunks
REWRITE_PAUSE_S = 3.0  # between uncached model calls, to stay under 8,000 tokens a minute
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
    parser.add_argument(
        "--rerank-query",
        choices=("question", "rewrite"),
        default="question",
        help="rerank against the question, or against the first multi-query rewrite",
    )
    parser.add_argument("--neighbours", type=int, default=0, help="chunks added on each side")
    parser.add_argument("--neighbours-top", type=int, default=5, help="hits that get neighbours")
    parser.add_argument("--setting", choices=("oracle", "corpus", "understood"), default="oracle")
    parser.add_argument(
        "--rewrite", help="rewrites to search too: multi, hyde, decompose (comma-separated) or all"
    )
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

    kinds: tuple[Rewrite, ...] = ()
    if args.rewrite:
        asked = REWRITES if args.rewrite == "all" else tuple(args.rewrite.split(","))
        kinds = tuple(kind for kind in REWRITES if kind in asked)
        if not kinds or len(kinds) != len(set(asked)):
            parser.error(f"--rewrite takes {', '.join(REWRITES)} or all")
    llm: PacedLLM | None = None
    cache: CachedLLM | None = None
    if kinds:
        models: dict[ModelRole, str] = {
            "fast": settings.llm_fast_model,
            "strong": settings.llm_strong_model,
        }
        cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "llm.jsonl", models)
        llm = PacedLLM(cache, pause_s=REWRITE_PAUSE_S)

    corpus = {q.doc_name for q in fb.load_questions(root)}
    filings = filings_from(doc for name, doc in fb.load_documents(root).items() if name in corpus)
    companies = read_companies()
    matcher = CompanyMatcher([c.name for c in companies], {c.name: c.ticker for c in companies})

    predictions: dict[str, list[retrieval.PageRef]] = {}
    latency: dict[str, float] = {}
    searched: dict[str, list[str] | None] = {}
    rewrite_ms: dict[str, float] = {}
    sources: dict[str, dict[str, int]] = {}
    tokens = 0
    for question in questions:
        searches = [Search(question.question)]
        if llm is not None:
            llm.reset()
            searches = expand(llm, question.question, kinds)
            rewrite_ms[question.id] = llm.latency_s * 1000
            tokens += llm.prompt_tokens + llm.completion_tokens
        sources[question.id] = dict(Counter(search.source for search in searches))
        started = time.perf_counter()
        documents: list[str] | None = None
        if args.setting == "oracle":
            documents = [question.doc_name]
        elif args.setting == "understood":
            documents = resolve(understand(question.question, matcher), filings)
        searched[question.id] = documents
        rankings = [
            searcher.search(search.text, args.mode, FETCH, documents, passage=search.passage)
            for search in searches
        ]
        hits = rankings[0] if len(rankings) == 1 else reciprocal_rank_fusion(rankings)[:FETCH]
        if reranker is not None:
            rewrites = [search.text for search in searches if search.source == "multi"]
            focus = (
                rewrites[0] if args.rerank_query == "rewrite" and rewrites else question.question
            )
            hits = rerank(reranker, focus, hits, args.rerank_top)
        if args.neighbours:
            hits = with_neighbours(searcher, hits, args.neighbours_top, args.neighbours)
        predictions[question.id] = ranked_pages(hits, PAGES)
        search_ms = (time.perf_counter() - started) * 1000
        latency[question.id] = search_ms + rewrite_ms.get(question.id, 0.0)

    rows = retrieval.score(questions, predictions)
    for row in rows:
        row["latency_ms"] = round(latency[row["id"]], 1)
        row["searched_filings"] = searched[row["id"]]
        if kinds:
            row["searches"] = sources[row["id"]]
            row["rewrite_ms"] = round(rewrite_ms[row["id"]], 1)
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
    if args.setting == "understood":
        resolved = [(q, searched[q.id]) for q in questions]
        system |= {
            "query_understanding": {
                "resolved": sum(docs is not None for _, docs in resolved),
                "own_filing_included": sum(
                    docs is not None and q.doc_name in docs for q, docs in resolved
                ),
                "mean_filings": round(
                    statistics.mean(len(docs) for _, docs in resolved if docs), 2
                ),
            }
        }
    if kinds and cache is not None:
        system |= {
            "rewrite": {
                "kinds": list(kinds),
                "prompt_version": REWRITE_PROMPT_VERSION,
                "model": settings.llm_fast_model,
                "fusion": f"RRF, k = {RRF_K}, over the question and every rewrite",
                "tokens": tokens,
                "cache": {"hits": cache.hits, "misses": cache.misses},
                "latency_ms_p50": round(float(np.percentile(list(rewrite_ms.values()), 50)), 1),
            }
        }
    if args.mode == "hybrid":
        system |= {"rrf_k": searcher.rrf_k, "candidates_per_ranking": searcher.candidates}
        if weights:
            system |= {"rrf_weights": {"dense": weights[0], "bm25": weights[1]}}
    if reranker is not None:
        system |= {
            "reranker": reranker.model_id,
            "rerank_top": args.rerank_top,
            "rerank_query": args.rerank_query,
        }
    if args.neighbours:
        system |= {"neighbours": args.neighbours, "neighbours_top": args.neighbours_top}

    run = args.run or "-".join(
        part
        for part in (
            args.collection.removeprefix("fb_"),
            args.mode,
            f"w{args.rrf_weights.replace(',', '-')}" if args.rrf_weights else "",
            f"rerank-{args.rerank}" if args.rerank else "",
            "rq" if args.rerank and args.rerank_query == "rewrite" else "",
            f"nb{args.neighbours}" if args.neighbours else "",
            f"rw-{'-'.join(kinds)}" if kinds else "",
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
