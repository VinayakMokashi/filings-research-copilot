"""Measure how often the answer model's context holds an evidence page (step 3.3).

Runs the doc agent's retrieval for every dev question (query understanding, three cached
rewrites, fused dense search), then packs the results into contexts of several token
budgets, with and without the other parts of split pages. Scores, per question:

- `context_hit`: at least one evidence page is in the context;
- `context_recall`: the share of the question's evidence pages in the context;
- `sources` and `tokens`: how large the context is.

Writes one run per configuration to eval/results/context/<run>/dev/.

Usage: uv run poe eval-context     (needs the page index and the rewrite cache or the key)
"""

from __future__ import annotations

import argparse
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.answer.agent import build_agent
from copilot.answer.context import context_pages
from copilot.config import get_settings
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.retrieval import gold_pages
from copilot.eval.splits import load_split
from copilot.logs import configure_logging

BUDGETS = (1500, 3000, 4500)
METRICS = ["context_hit", "context_recall"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    agent = build_agent(settings)
    retrievals = {question.id: agent.retrieve(question.question) for question in questions}

    for siblings in (False, True):
        agent.siblings = siblings
        for budget in BUDGETS:
            rows: list[dict[str, Any]] = []
            for question in questions:
                sources = agent.context(retrievals[question.id], budget)
                covered = context_pages(sources)
                gold = gold_pages(question)
                found = sum((page.doc_name, page.page) in covered for page in gold)
                rows.append(
                    {
                        "id": question.id,
                        "question_type": question.question_type,
                        "context_hit": float(found > 0),
                        "context_recall": found / len(gold),
                        "sources": len(sources),
                        "tokens": sum(source.tokens for source in sources),
                    }
                )
            run = f"page-rw-all-understood-b{budget}{'-siblings' if siblings else ''}"
            summary = RunSummary(
                suite="context",
                run=run,
                split="dev",
                created=datetime.now(UTC),
                questions=len(rows),
                test_split_opened=False,
                system={
                    "collection": "fb_page_bge-small",
                    "retrieval": "understood filings, three rewrites, fused dense search",
                    "budget_tokens": budget,
                    "split_page_parts": siblings,
                    "mean_sources": round(statistics.mean(r["sources"] for r in rows), 2),
                    "mean_tokens": round(statistics.mean(r["tokens"] for r in rows)),
                },
                metrics=summarise(rows, METRICS),
                by={"question_type": summarise_by(rows, METRICS, "question_type")},
            )
            write_run(args.results_dir / "context" / run / "dev", summary, rows)
            hit, recall = summary.metrics["context_hit"], summary.metrics["context_recall"]
            print(
                f"{run}: hit {hit.mean:.3f} ({hit.low:.2f} to {hit.high:.2f}), "
                f"recall {recall.mean:.3f}, sources {summary.system['mean_sources']}, "
                f"tokens {summary.system['mean_tokens']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
