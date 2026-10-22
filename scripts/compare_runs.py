"""Compare two eval runs on one metric with a paired test (ADR-0007).

Usage:
  uv run poe compare-runs BASELINE_DIR CANDIDATE_DIR --metric recall@10
  uv run poe compare-runs A B --metric correct --where question_type=metrics-generated
"""

from __future__ import annotations

import argparse
from pathlib import Path

from copilot.eval.report import compare_runs, outcome_table

ALPHA = 0.05


def condition(text: str) -> tuple[str, str]:
    """Split FIELD=VALUE, as in question_type=metrics-generated."""
    field, sep, value = text.partition("=")
    if not sep or not field:
        raise argparse.ArgumentTypeError(f"expected FIELD=VALUE, got {text!r}")
    return field, value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("baseline", type=Path, help="run directory of the current baseline")
    parser.add_argument("candidate", type=Path, help="run directory of the change being tested")
    parser.add_argument("--metric", required=True, help="a metric name from items.jsonl")
    parser.add_argument(
        "--where",
        type=condition,
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="compare only the questions with this value, e.g. question_type=metrics-generated",
    )
    args = parser.parse_args(argv)
    where = dict(args.where)

    result = compare_runs(args.baseline, args.candidate, args.metric, where=where)
    diff = result.difference
    if result.p_value >= ALPHA:
        verdict = "no significant difference"
    elif diff.mean > 0:
        verdict = "significant improvement"
    else:
        verdict = "significant regression"

    scope = "".join(f", {field} = {value}" for field, value in where.items())
    print(f"{args.metric} on {diff.n} paired questions{scope}")
    print(f"  baseline   {result.mean_a:.3f}")
    print(f"  candidate  {result.mean_b:.3f}")
    print(
        f"  difference {diff.mean:+.3f} ({diff.confidence:.0%} interval {diff.low:+.3f} to "
        f"{diff.high:+.3f})"
    )
    print(f"  p-value    {result.p_value:.4f} (paired permutation test)")
    print(f"  verdict    {verdict} at alpha {ALPHA}")
    table = outcome_table(args.baseline, args.candidate, args.metric, where=where)
    if table is not None:
        print("  questions  " + ", ".join(f"{name} {count}" for name, count in table.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
