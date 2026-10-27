"""A cascade of two routers, computed from their runs on the same questions (step 7.2).

The cascade takes the first router's route when its confidence reaches a threshold, and
asks the second router otherwise. Both routers decide each question the same way every
time (the classifier is a fixed model; the LLM router's calls are cached at temperature
0), so the cascade routes each question exactly as the two runs did, and needs no new
model calls. For each threshold it writes a run of its own, eval/results/routing/<name>/
<split>/ (items.jsonl, summary.json, summary.md), so `poe compare-runs` can pair it with
either router; and a table of every threshold to eval/results/routing/_comparisons/.

A question sent on costs the first router's time plus the second's, and the second's money.

Usage:
  uv run python scripts/simulate_cascade.py eval/results/routing/classifier-v2/dev \
      eval/results/routing/llm-gpt-oss-120b/dev --thresholds 0.9 0.99 --name cascade-classifier-v2
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run

METRICS = ["accuracy", "llm_used"]


def read_items(directory: Path) -> dict[str, dict[str, Any]]:
    lines = (directory / "items.jsonl").read_text(encoding="utf-8").splitlines()
    return {item["id"]: item for item in map(json.loads, lines)}


def cascade(
    first: dict[str, dict[str, Any]], second: dict[str, dict[str, Any]], threshold: float
) -> list[dict[str, Any]]:
    """Each question routed by the cascade at `threshold`, in the first run's order."""
    if set(first) != set(second):
        raise ValueError("The two runs must cover the same questions.")
    rows = []
    for qid, one in first.items():
        two = second[qid]
        sent_on = (one.get("confidence") or 0.0) < threshold
        chosen = two if sent_on else one
        rows.append(
            {
                "id": qid,
                "route": one["route"],
                "origin": one.get("origin"),
                "predicted": chosen["predicted"],
                "accuracy": float(chosen["predicted"] == one["route"]),
                "confidence": one.get("confidence"),
                "llm_used": float(sent_on),
                "latency_s": round(one["latency_s"] + (two["latency_s"] if sent_on else 0.0), 4),
                "cost_usd": (two.get("cost_usd") or 0.0) if sent_on else 0.0,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("first", type=Path, help="the first router's run directory")
    parser.add_argument("second", type=Path, help="the second router's run directory")
    parser.add_argument("--thresholds", type=float, nargs="+", required=True)
    parser.add_argument("--name", required=True, help="run name prefix, e.g. cascade-classifier")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    first, second = read_items(args.first), read_items(args.second)
    split = args.first.name
    table = []
    for threshold in args.thresholds:
        rows = cascade(first, second, threshold)
        run = f"{args.name}-t{threshold:g}"
        latencies = sorted(row["latency_s"] for row in rows)
        summary = RunSummary(
            suite="routing",
            run=run,
            split=split,
            created=datetime.now(UTC),
            questions=len(rows),
            test_split_opened=split == "test",
            system={
                "router": "cascade (simulated)",
                "first": str(args.first.as_posix()),
                "second": str(args.second.as_posix()),
                "threshold": threshold,
                "latency_s": {
                    "p50": round(statistics.median(latencies), 4),
                    "p95": round(latencies[int(0.95 * (len(latencies) - 1))], 4),
                },
                "cost_usd_per_question": round(statistics.mean(r["cost_usd"] for r in rows), 7),
            },
            metrics=summarise(rows, METRICS),
            by={"route": summarise_by(rows, METRICS, "route")},
        )
        write_run(args.results_dir / "routing" / run / split, summary, rows)
        accuracy, used = summary.metrics["accuracy"], summary.metrics["llm_used"]
        table.append(
            {
                "threshold": threshold,
                "run": run,
                "accuracy": round(accuracy.mean, 4),
                "accuracy_low": round(accuracy.low, 4),
                "accuracy_high": round(accuracy.high, 4),
                "sent_on": round(used.mean, 4),
                "errors": sum(1 for row in rows if not row["accuracy"]),
                "latency_p50_s": summary.system["latency_s"]["p50"],
                "cost_usd_per_question": summary.system["cost_usd_per_question"],
            }
        )
        print(table[-1])

    out = args.results_dir / "routing" / "_comparisons" / f"{args.name}-{split}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(
        json.dumps(table, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        f"# {args.name} ({split}): the first router's route above a confidence threshold",
        "",
        f"First `{args.first.parent.name}`, second `{args.second.parent.name}`, "
        f"{len(first)} questions; 95% bootstrap intervals.",
        "",
        "| Threshold | Accuracy | Sent on | Errors | Median latency | Cost a question |",
        "|---|---|---|---|---|---|",
        *(
            f"| {row['threshold']:g} | {row['accuracy']:.3f} ({row['accuracy_low']:.3f} to "
            f"{row['accuracy_high']:.3f}) | {row['sent_on']:.0%} | {row['errors']} | "
            f"{row['latency_p50_s'] * 1000:.0f} ms | ${row['cost_usd_per_question']:.6f} |"
            for row in table
        ),
        "",
    ]
    out.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Wrote {out}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
