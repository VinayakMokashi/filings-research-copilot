"""Run a router over the routing set and score it (step 5.2), resumably.

Routers (`--router`):

- `semantic`: bge-small similarity to labelled examples, the routing set's dev questions:
  a similarity-weighted vote among the `--k` nearest, or the nearest route centroid
  (`--method centroid`), optionally with company names and years masked (`--mask
  entities`). Each question is routed with its own seed group (the seed and its two
  paraphrases) left out of the examples, because a paraphrase of the question among them
  would give its route away. Test seeds aren't among the examples, so on the test split
  nothing is left out.
- `llm`: the route definitions, the labelling rules, the database's measures and a few
  prompt examples, on a model role (`--role`; FRC_LLM_FAST_MODEL picks the fast model).
  Calls are cached in data/cache/router.jsonl and paced for the free tier.
- `cascade`: the semantic route when its confidence reaches `--threshold`, the LLM route
  otherwise.

Each decision is appended to data/processed/routing/<run>/<split>/decisions.jsonl as it
arrives, and a rerun skips the questions already there; a run stopped by a quota or an
outage exits with 1, so run it again. Then eval/results/routing/<run>/<split>/ gets
items.jsonl (each decision with its latency, tokens and cost), summary.json, summary.md
and confusion.md.

Usage:
  uv run poe run-router --router semantic --run semantic-k5
  uv run poe run-router --router semantic --k 1 --run semantic-k1
  uv run poe run-router --router semantic --mask entities --method centroid --run NAME
  uv run poe run-router --router llm --run llm-qwen3.8-27b                (needs GROQ_API_KEY)
  uv run poe run-router --router cascade --threshold 1.0 --run cascade-k5-qwen3.8-27b
  uv run poe run-router ... --split test --allow-test                 # milestone evaluations only

Set FRC_LLM_FAST_MODEL (to groq/openai/gpt-oss-20b, say) to run the LLM router on another
model, under a run name of its own.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.agents.router import (
    PROMPT_VERSION,
    CascadeRouter,
    K,
    LLMRouter,
    RouteDecision,
    SemanticRouter,
    entity_mask,
)
from copilot.config import Settings, get_settings
from copilot.eval import routing
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.splits import HeldOutError
from copilot.ingest.embed import BGE_MODEL, FastEmbedDense
from copilot.ingest.universe import read_companies
from copilot.llm import LLMError, LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging
from copilot.retrieval.query import CompanyMatcher

CACHE_FILE = "router.jsonl"

Decide = Callable[[routing.RoutingQuery, Sequence[int]], RouteDecision]


def llm_client(settings: Settings) -> PacedLLM:
    """The gateway behind the router's own cache file, paced for the free tier."""
    models: dict[ModelRole, str] = {
        "fast": settings.llm_fast_model,
        "strong": settings.llm_strong_model,
    }
    cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / CACHE_FILE, models)
    return PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)


def seed_groups(
    examples: Sequence[routing.RoutingQuery], queries: Sequence[routing.RoutingQuery]
) -> dict[str, list[int]]:
    """For each query, the positions of the examples from its own seed group."""
    positions: dict[str, list[int]] = defaultdict(list)
    for position, example in enumerate(examples):
        positions[example.seed].append(position)
    return {query.id: positions.get(query.seed, []) for query in queries}


def configuration(args: argparse.Namespace, settings: Settings) -> dict[str, Any]:
    """What the run is, recorded with its decisions and in its summary."""
    config: dict[str, Any] = {"router": args.router}
    if args.router in ("semantic", "cascade"):
        config |= {
            "embedder": BGE_MODEL,
            "method": args.method,
            "k": args.k if args.method == "vote" else None,
            "mask": args.mask,
            "instruction": args.instruction,
            "examples": "routing set dev, each question's own seed group left out",
        }
    if args.router in ("llm", "cascade"):
        model = settings.llm_fast_model if args.role == "fast" else settings.llm_strong_model
        config |= {"model": model, "prompt_version": PROMPT_VERSION}
    if args.router == "cascade":
        config["threshold"] = args.threshold
    return config


def build(
    args: argparse.Namespace, settings: Settings, examples: Sequence[routing.RoutingQuery]
) -> Decide:
    if args.router == "llm":
        llm = LLMRouter(llm_client(settings), role=args.role)
        return lambda query, _exclude: llm.route(query.query)
    mask = None
    if args.mask == "entities":
        companies = read_companies()
        mask = entity_mask(
            CompanyMatcher([c.name for c in companies], {c.name: c.ticker for c in companies})
        )
    semantic = SemanticRouter(
        FastEmbedDense(cache_dir=settings.data_dir / "models"),
        [(example.query, example.route) for example in examples],
        method=args.method,
        k=args.k,
        mask=mask,
        instruction=args.instruction,
    )
    if args.router == "semantic":
        return lambda query, exclude: semantic.route(query.query, exclude)
    cascade = CascadeRouter(
        semantic,
        LLMRouter(llm_client(settings), role=args.role),
        threshold=args.threshold,
        fallback_on_error=False,
    )
    return lambda query, exclude: cascade.route(query.query, exclude)


def read_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def percentile(values: Sequence[float], share: float) -> float:
    """The nearest-rank percentile of `values` (0 < share <= 1)."""
    ordered = sorted(values)
    return ordered[max(math.ceil(share * len(ordered)) - 1, 0)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--router", choices=("semantic", "llm", "cascade"), required=True)
    parser.add_argument("--run", required=True, help="run name")
    parser.add_argument("--method", choices=("vote", "centroid"), default="vote")
    parser.add_argument("--k", type=int, default=K, help="examples that vote (semantic)")
    parser.add_argument(
        "--mask", choices=("none", "entities"), default="none", help="mask companies and years"
    )
    parser.add_argument(
        "--instruction", action="store_true", help="embed questions with bge's search instruction"
    )
    parser.add_argument("--role", choices=("fast", "strong"), default="fast")
    parser.add_argument(
        "--threshold", type=float, default=1.0, help="vote share the semantic route needs"
    )
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    try:
        queries = routing.load_queries(args.split, allow_test=args.allow_test)
    except HeldOutError:
        print("The routing test split is held out. Add --allow-test only for a milestone run.")
        return 2
    examples = routing.load_queries("dev")
    config = configuration(args, settings)

    directory = settings.data_dir / "processed" / "routing" / args.run / args.split
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "config.json"
    if config_path.exists():
        recorded = json.loads(config_path.read_text(encoding="utf-8"))
        if recorded != config:
            print(f"{args.run} was started as {recorded}; give this configuration a new --run.")
            return 2
    else:
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")

    decisions_path = directory / "decisions.jsonl"
    done = read_decisions(decisions_path)
    todo = [query for query in queries if query.id not in done]
    print(f"{len(queries)} questions, {len(done)} already routed, {len(todo)} to go")
    if todo:
        decide = build(args, settings, examples)
        groups = seed_groups(examples, queries)
        with decisions_path.open("a", encoding="utf-8", newline="\n") as out:
            for number, query in enumerate(todo, start=1):
                try:
                    decision = decide(query, groups[query.id])
                except LLMError as exc:
                    reason = "the model's quota is used up" if exc.rate_limited else str(exc)[:200]
                    print(f"Stopped at {query.id}: {reason}. Run again later.")
                    return 1
                record = {"id": query.id, **asdict(decision)}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                done[query.id] = record
                print(f"  {number}/{len(todo)} {query.id}: {decision.route}")

    rows = routing.score(queries, {query.id: str(done[query.id]["route"]) for query in queries})
    for row in rows:
        made = done[row["id"]]
        row |= {
            "confidence": made["confidence"],
            "scores": made["scores"],
            "reason": made["reason"],
            "model": made["model"],
            "llm_used": float(made["model"] is not None),
            "latency_s": round(made["latency_s"], 4),
            "prompt_tokens": made["prompt_tokens"],
            "completion_tokens": made["completion_tokens"],
            "cost_usd": made["cost_usd"],
            "error": made["error"],
        }

    metrics = ["accuracy", "llm_used"] if args.router == "cascade" else ["accuracy"]
    latencies = [row["latency_s"] for row in rows]
    costs = [row["cost_usd"] for row in rows]
    system = {
        **config,
        "latency_s": {
            "p50": round(statistics.median(latencies), 4),
            "p95": round(percentile(latencies, 0.95), 4),
        },
        "mean_tokens": round(
            statistics.mean(row["prompt_tokens"] + row["completion_tokens"] for row in rows)
        ),
        "cost_usd_per_question": round(statistics.mean(costs), 7)
        if all(cost is not None for cost in costs)
        else None,
        "errors": sum(1 for row in rows if row["error"]),
    }
    summary = RunSummary(
        suite="routing",
        run=args.run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system=system,
        metrics=summarise(rows, metrics),
        by={
            "route": summarise_by(rows, metrics, "route"),
            "origin": summarise_by(rows, metrics, "origin"),
        },
    )
    results = args.results_dir / "routing" / args.run / args.split
    write_run(results, summary, rows)
    title = f"routing: {args.run} ({args.split})"
    matrix = routing.render_confusion(routing.confusion(rows), title)
    (results / "confusion.md").write_text(matrix, encoding="utf-8", newline="\n")
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(json.dumps(system["latency_s"]), f"errors {system['errors']}")
    print(f"Wrote {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
