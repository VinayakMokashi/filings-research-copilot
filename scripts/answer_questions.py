"""Answer FinanceBench questions with the doc agent, resumably (steps 3.3 to 3.5).

Each answer is written as it arrives to data/processed/answers/<run>/<split>/answers.jsonl,
with its sources, citations, calculations and what it cost; those files hold filing text,
so they stay local. A rerun skips questions already answered, so a run cut short by a
daily quota simply continues the next day. Once every question has an answer, a summary of
the automatic measures goes to eval/results/answers/<run>/<split>/ (ids and numbers only):

- `answered`: the agent gave an answer rather than saying the sources lack it;
- `retried`: the first answer said something was missing, so the agent searched again;
- `uncited`: an answer without a single valid citation;
- `context_hit`: an evidence page was among the sources;
- `cites_evidence`: at least one cited source is an evidence page (a lower bound on
  citation quality, since other pages can state the same figure);
- `invalid_citations`, `calculation_errors`: citations to missing sources, failed sums.

Correctness and faithfulness come from the judge (step 3.6).

Usage: uv run poe answer-questions --limit 10        (needs GROQ_API_KEY)
       uv run poe answer-questions                   (all dev questions, resumable)
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.answer.agent import AgentAnswer, build_agent
from copilot.answer.generate import PROMPT_VERSION
from copilot.config import get_settings
from copilot.eval.financebench import Question
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.retrieval import gold_pages
from copilot.eval.splits import load_split
from copilot.logs import configure_logging

METRICS = ["answered", "retried", "uncited", "context_hit", "cites_evidence"]


def record(question: Question, result: AgentAnswer) -> dict[str, Any]:
    """Everything about one answer, for the local answers file."""
    answer = result.answer
    return {
        "id": question.id,
        "question_type": question.question_type,
        "answerable": answer.answerable,
        "text": answer.text,
        "missing": answer.missing,
        "error": answer.error,
        "sources": [asdict(source) for source in answer.sources],
        "cited": answer.cited,
        "invalid_citations": answer.invalid_citations,
        "calculations": [asdict(calculation) for calculation in answer.calculations],
        "filings": result.retrieval.filings,
        "searches": dict(Counter(search.source for search in result.retrieval.searches)),
        "retried": result.retried,
        "first_missing": result.first.missing if result.first else None,
        "model": answer.model,
        "prompt_version": PROMPT_VERSION,
        "prompt_tokens": answer.prompt_tokens + (result.first.prompt_tokens if result.first else 0),
        "completion_tokens": answer.completion_tokens
        + (result.first.completion_tokens if result.first else 0),
        "latency_s": round(answer.latency_s + (result.first.latency_s if result.first else 0), 3),
    }


def scores(question: Question, item: dict[str, Any]) -> dict[str, Any]:
    """The automatic measures for one answer; no text."""
    gold = {(page.doc_name, page.page) for page in gold_pages(question)}
    sources = {s["number"]: (s["doc_name"], s["page"]) for s in item["sources"]}
    cited = [sources[number] for number in item["cited"] if number in sources]
    return {
        "id": question.id,
        "question_type": question.question_type,
        "answered": float(item["answerable"]),
        "retried": float(item["retried"]),
        "uncited": float(item["answerable"] and not item["cited"]),
        "context_hit": float(any(page in gold for page in sources.values())),
        "cites_evidence": float(any(page in gold for page in cited)),
        "citations": len(item["cited"]),
        "invalid_citations": len(item["invalid_citations"]),
        "calculation_errors": sum(c["error"] is not None for c in item["calculations"]),
        "prompt_tokens": item["prompt_tokens"],
        "completion_tokens": item["completion_tokens"],
        "latency_s": item["latency_s"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", default="doc-agent-v3", help="run name")
    parser.add_argument("--limit", type=int, help="answer only the first N questions")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")[: args.limit]
    path = settings.data_dir / "processed" / "answers" / args.run / "dev" / "answers.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                done[item["id"]] = item

    agent = build_agent(settings)
    todo = [question for question in questions if question.id not in done]
    print(f"{len(questions)} questions, {len(done)} already answered, {len(todo)} to go")
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            item = record(question, agent.answer(question.question))
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = item
            print(f"  {number}/{len(todo)} {question.id}: answered={item['answerable']}")

    rows = [scores(question, done[question.id]) for question in questions]
    summary = RunSummary(
        suite="answers",
        run=args.run,
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "agent": "understood filings, three rewrites, fused dense search, page chunks",
            "retry": "on a refusal, search for what is missing across the company's filings",
            "retry_budget_tokens": agent.retry_budget,
            "context_budget_tokens": agent.budget,
            "answer_model": settings.llm_strong_model,
            "rewrite_model": settings.llm_fast_model,
            "prompt_version": PROMPT_VERSION,
            "mean_prompt_tokens": round(statistics.mean(r["prompt_tokens"] for r in rows)),
            "mean_completion_tokens": round(statistics.mean(r["completion_tokens"] for r in rows)),
            "invalid_citations": sum(r["invalid_citations"] for r in rows),
            "calculation_errors": sum(r["calculation_errors"] for r in rows),
            "limit": args.limit,
        },
        metrics=summarise(rows, METRICS),
        by={"question_type": summarise_by(rows, METRICS, "question_type")},
    )
    directory = args.results_dir / "answers" / args.run / "dev"
    write_run(directory, summary, rows)
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(f"Wrote {directory} and {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
