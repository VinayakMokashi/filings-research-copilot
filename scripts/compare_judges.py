"""How often two judges agree on the same answers: two models, or one model on two providers.

Reads two judges' verdicts on one answers run, from data/processed/judgements/<run>/<judge>/
(or data/processed/faithfulness/<run>/<judge>/ with `--suite faithfulness`), and writes to
eval/results/judge-agreement/<run>--<first>--vs--<second>/dev/:

- `agree`: both judges give the same verdict (with a bootstrap interval);
- `cohens_kappa`: agreement beyond chance, with a bootstrap interval;
- `first_positive`, `second_positive`: how often each says correct (or faithful), to show a
  stricter judge, with McNemar's exact test of the difference;
- the confusion counts, and each judge's errors (replies that couldn't be read, which count
  against the answer, so a judge that errs often looks strict).

Usage: uv run poe compare-judges --run doc-agent-v4-full qwen3.8-27b-p2 qwen-3.8-27b-p2
       uv run poe compare-judges --run doc-agent-v4-full qwen3.8-27b-f1 qwen-3.8-27b-f1 \
           --suite faithfulness
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.report import (
    RESULTS_DIR,
    MetricSummary,
    RunSummary,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import load_split
from copilot.eval.stats import kappa_interval, mcnemar_exact

METRICS = ["agree", "first_positive", "second_positive"]
# suite: (directory under data/processed, file name, verdict field, the positive verdict)
SUITES: dict[str, tuple[str, str, str, str]] = {
    "correctness": ("judgements", "judgements.jsonl", "verdict", "correct"),
    "faithfulness": ("faithfulness", "checks.jsonl", "faithful", "True"),
}


def read_verdicts(path: Path, field: str) -> tuple[dict[str, str], int]:
    """Each answer's verdict as text, and how many of the judge's replies were errors."""
    lines = path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    errors = sum(record.get("error") is not None for record in records)
    return {record["id"]: str(record[field]) for record in records}, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("judges", nargs=2, metavar="JUDGE", help="the two judges' names")
    parser.add_argument("--run", required=True, help="the answers run both judges graded")
    parser.add_argument("--suite", choices=sorted(SUITES), default="correctness")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    first, second = args.judges
    folder, file_name, field, positive = SUITES[args.suite]

    settings = get_settings()
    types = {
        q.id: q.question_type for q in load_split("dev", settings.data_dir / "raw" / "financebench")
    }
    base = settings.data_dir / "processed" / folder / args.run
    a, a_errors = read_verdicts(base / first / file_name, field)
    b, b_errors = read_verdicts(base / second / file_name, field)
    ids = [qid for qid in types if qid in a and qid in b]
    rows: list[dict[str, Any]] = [
        {
            "id": qid,
            "question_type": types[qid],
            "agree": float(a[qid] == b[qid]),
            "first_positive": float(a[qid] == positive),
            "second_positive": float(b[qid] == positive),
        }
        for qid in ids
    ]
    kappa = kappa_interval([a[qid] for qid in ids], [b[qid] for qid in ids])
    metrics = summarise(rows, METRICS)
    metrics["cohens_kappa"] = MetricSummary(mean=kappa.mean, low=kappa.low, high=kappa.high)
    p_value = mcnemar_exact(
        [a[qid] == positive for qid in ids], [b[qid] == positive for qid in ids]
    )
    confusion = Counter(f"{first} {a[qid]}, {second} {b[qid]}" for qid in ids)
    summary = RunSummary(
        suite="judge-agreement",
        run=f"{args.run}--{first}--vs--{second}",
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "answers_run": args.run,
            "suite": args.suite,
            "first": first,
            "second": second,
            "errors": {first: a_errors, second: b_errors},
            "positive_difference_mcnemar_p": round(p_value, 4),
            "disagreements": [qid for qid in ids if a[qid] != b[qid]],
            "confusion": dict(sorted(confusion.items())),
        },
        metrics=metrics,
        by={"question_type": summarise_by(rows, METRICS, "question_type")},
    )
    directory = args.results_dir / "judge-agreement" / f"{args.run}--{first}--vs--{second}" / "dev"
    write_run(directory, summary, rows)
    print(
        f"{first} vs {second} on {len(rows)} answers: agree {metrics['agree'].mean:.3f}, "
        f"kappa {kappa.mean:.3f} ({kappa.low:.2f} to {kappa.high:.2f}); {positive}: "
        f"{metrics['first_positive'].mean:.3f} vs {metrics['second_positive'].mean:.3f} "
        f"(McNemar p = {p_value:.3f}); errors {a_errors} and {b_errors} -> {directory}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
