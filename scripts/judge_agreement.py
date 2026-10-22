"""How often a judge agrees with the reference labels about which answers are correct (3.6).

Reads the reference labels in eval/labels/answer-correctness.jsonl (one line per labelled
answer: its id, the answers run, who labelled it, and "correct", "incorrect" or "unsure")
and each judge's verdicts for the same answers. Unsure labels are left out. Writes, per
judge, to eval/results/judge-agreement/<run>--<judge>/dev/:

- `agree`: the judge's verdict matches the label (with a bootstrap interval);
- `cohens_kappa`: agreement beyond chance, with a bootstrap interval;
- `labeller_correct`, `judge_correct`: how often each says correct, to show a lenient or a
  strict judge;
- the confusion counts, and who the labeller was.

Usage: uv run poe judge-agreement --run doc-agent-v3-full --judge qwen3.8-27b-p2
       uv run poe judge-agreement --run doc-agent-v3-full --judge qwen3.8-27b-p2 \
           --judge gpt-oss-120b-p2        (several judges against the same labels)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.labels import labellers, read_labels
from copilot.eval.report import (
    RESULTS_DIR,
    MetricSummary,
    RunSummary,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import load_split
from copilot.eval.stats import kappa_interval

LABELS_FILE = Path("eval/labels/answer-correctness.jsonl")
METRICS = ["agree", "labeller_correct", "judge_correct"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="the answers run that was labelled")
    parser.add_argument("--judge", action="append", required=True, help="judge name, repeatable")
    parser.add_argument("--labels", type=Path, default=LABELS_FILE)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    types = {
        q.id: q.question_type for q in load_split("dev", settings.data_dir / "raw" / "financebench")
    }
    labels = read_labels(args.labels, args.run)
    for name in args.judge:
        path = settings.data_dir / "processed" / "judgements" / args.run / name / "judgements.jsonl"
        verdicts = {item["id"]: item["verdict"] for item in read_jsonl(path)}
        ids = [qid for qid in types if qid in labels and qid in verdicts]
        missing = sorted(set(labels) - set(verdicts))
        if missing:
            print(f"{name}: no verdict yet for {len(missing)} labelled answers; skipped them")
        rows = [
            {
                "id": qid,
                "question_type": types[qid],
                "agree": float(verdicts[qid] == labels[qid]),
                "labeller_correct": float(labels[qid] == "correct"),
                "judge_correct": float(verdicts[qid] == "correct"),
            }
            for qid in ids
        ]
        kappa = kappa_interval([labels[qid] for qid in ids], [verdicts[qid] for qid in ids])
        metrics = summarise(rows, METRICS)
        metrics["cohens_kappa"] = MetricSummary(mean=kappa.mean, low=kappa.low, high=kappa.high)
        confusion = Counter(f"labeller {labels[qid]}, judge {verdicts[qid]}" for qid in ids)
        summary = RunSummary(
            suite="judge-agreement",
            run=f"{args.run}--{name}",
            split="dev",
            created=datetime.now(UTC),
            questions=len(rows),
            test_split_opened=False,
            system={
                "answers_run": args.run,
                "judge": name,
                "labelled": len(labels),
                "labellers": labellers(args.labels, args.run),
                "confusion": dict(sorted(confusion.items())),
            },
            metrics=metrics,
            by={"question_type": summarise_by(rows, METRICS, "question_type")},
        )
        directory = args.results_dir / "judge-agreement" / f"{args.run}--{name}" / "dev"
        write_run(directory, summary, rows)
        print(
            f"{name}: agree {metrics['agree'].mean:.3f}, kappa {kappa.mean:.3f} "
            f"({kappa.low:.2f} to {kappa.high:.2f}) on {len(rows)} answers -> {directory}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
