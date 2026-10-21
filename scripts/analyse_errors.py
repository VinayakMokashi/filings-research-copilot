"""Sort a run's answers by outcome and error category, and add up what they cost (step 3.7).

Joins the run's answers, a judge's verdicts and, when given, the faithfulness checks, all
read from data/processed/, and writes ids, outcomes, categories and costs (no text) to
eval/results/errors/<run>--<judge>/dev/:

- items.jsonl: per question, the outcome, the category (`copilot.eval.errors`), whether
  an evidence page was in the context, whether the answer was retried, faithful or
  uncited, failed calculations, tokens, latency and cost at list prices;
- summary.json and summary.md: categories by question type, and totals.

Usage: uv run poe analyse-errors --run doc-agent-v3-full --judge qwen3.8-27b-p2 \
           --faithfulness qwen3.8-27b-f1
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litellm

from copilot.config import get_settings
from copilot.eval.errors import CATEGORIES, categorise, unfilled
from copilot.eval.report import RESULTS_DIR
from copilot.eval.retrieval import gold_pages
from copilot.eval.splits import load_split


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """List price of the tokens in US dollars, from LiteLLM's price table."""
    prompt_cost, completion_cost = litellm.cost_per_token(
        model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return float(prompt_cost + completion_cost)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True)
    parser.add_argument("--judge", required=True, help="judge name, e.g. qwen3.8-27b-p2")
    parser.add_argument("--faithfulness", help="faithfulness judge name, e.g. qwen3.8-27b-f1")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    processed = settings.data_dir / "processed"
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    answers = read_jsonl(processed / "answers" / args.run / "dev" / "answers.jsonl")
    verdicts = read_jsonl(processed / "judgements" / args.run / args.judge / "judgements.jsonl")
    checks = (
        read_jsonl(processed / "faithfulness" / args.run / args.faithfulness / "checks.jsonl")
        if args.faithfulness
        else {}
    )

    rows = []
    for q in questions:
        if q.id not in answers or q.id not in verdicts:
            continue
        answer = answers[q.id]
        gold = {(page.doc_name, page.page) for page in gold_pages(q)}
        pages = {(s["doc_name"], s["page"]) for s in answer["sources"]}
        cited = {
            (s["doc_name"], s["page"]) for s in answer["sources"] if s["number"] in answer["cited"]
        }
        failed = sum(c["error"] is not None for c in answer["calculations"])
        outcome = verdicts[q.id]["verdict"]
        row: dict[str, Any] = {
            "id": q.id,
            "question_type": q.question_type,
            "outcome": outcome,
            "category": categorise(
                outcome,
                context_hit=bool(gold & pages),
                calculation_failed=failed > 0,
                text=answer["text"],
            ),
            "context_hit": bool(gold & pages),
            "cites_evidence": bool(gold & cited),
            "retried": answer["retried"],
            "uncited": answer["answerable"] and not answer["cited"],
            "failed_calculations": failed,
            "unfilled_placeholder": unfilled(answer["text"]),
            "prompt_tokens": answer["prompt_tokens"],
            "completion_tokens": answer["completion_tokens"],
            "latency_s": answer["latency_s"],
            "cost_usd": round(
                cost(answer["model"], answer["prompt_tokens"], answer["completion_tokens"]), 6
            ),
        }
        if q.id in checks:
            row["faithful"] = checks[q.id]["faithful"]
        rows.append(row)

    by_type: dict[str, Counter[str]] = {}
    for row in rows:
        by_type.setdefault(row["question_type"], Counter())[row["category"]] += 1
    totals = Counter(row["category"] for row in rows)
    latencies = sorted(row["latency_s"] for row in rows)
    summary = {
        "suite": "errors",
        "run": f"{args.run}--{args.judge}",
        "split": "dev",
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions": len(rows),
        "test_split_opened": False,
        "judge": args.judge,
        "faithfulness": args.faithfulness,
        "categories": {name: totals.get(name, 0) for name in CATEGORIES},
        "by_question_type": {
            group: {name: counts.get(name, 0) for name in CATEGORIES}
            for group, counts in sorted(by_type.items())
        },
        "outcomes": dict(Counter(row["outcome"] for row in rows)),
        "retried": sum(row["retried"] for row in rows),
        "failed_calculations": sum(row["failed_calculations"] for row in rows),
        "unfilled_placeholders": sum(row["unfilled_placeholder"] for row in rows),
        "mean_prompt_tokens": round(statistics.mean(row["prompt_tokens"] for row in rows)),
        "mean_completion_tokens": round(statistics.mean(row["completion_tokens"] for row in rows)),
        "model_latency_s": {
            "p50": round(statistics.median(latencies), 2),
            "p95": round(latencies[int(0.95 * (len(latencies) - 1))], 2),
        },
        "cost_usd": {
            "total": round(sum(row["cost_usd"] for row in rows), 4),
            "per_question": round(statistics.mean(row["cost_usd"] for row in rows), 6),
        },
    }

    directory = args.results_dir / "errors" / f"{args.run}--{args.judge}" / "dev"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "items.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for row in rows:
            out.write(json.dumps(row, sort_keys=True) + "\n")
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    types = sorted(by_type)
    lines = [
        f"# errors: {summary['run']} (dev)",
        "",
        f"{len(rows)} questions; outcomes by judge `{args.judge}`. Categories follow "
        "`copilot.eval.errors`.",
        "",
        "| Category | " + " | ".join(types) + " | All |",
        "|---|" + "---|" * (len(types) + 1),
    ]
    for name in CATEGORIES:
        counts = [str(by_type[group].get(name, 0)) for group in types]
        lines.append(f"| {name} | " + " | ".join(counts) + f" | {totals.get(name, 0)} |")
    lines += [
        "",
        f"Retried: {summary['retried']}. Failed calculations: {summary['failed_calculations']}. "
        f"Unfilled placeholders: {summary['unfilled_placeholders']}.",
        f"Model latency p50 {summary['model_latency_s']['p50']} s, "
        f"p95 {summary['model_latency_s']['p95']} s. "
        f"Cost at list prices: ${summary['cost_usd']['total']} in all, "
        f"${summary['cost_usd']['per_question']} a question.",
        "",
    ]
    (directory / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
