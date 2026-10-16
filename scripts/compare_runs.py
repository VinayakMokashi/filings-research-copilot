"""Compare two eval runs on one metric with a paired test (ADR-0007).

Usage:
  uv run poe compare-runs BASELINE_DIR CANDIDATE_DIR --metric recall@10
"""

from __future__ import annotations

import argparse
from pathlib import Path

from copilot.eval.report import compare_runs

ALPHA = 0.05


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("baseline", type=Path, help="run directory of the current baseline")
    parser.add_argument("candidate", type=Path, help="run directory of the change being tested")
    parser.add_argument("--metric", required=True, help="a metric name from items.jsonl")
    args = parser.parse_args(argv)

    result = compare_runs(args.baseline, args.candidate, args.metric)
    diff = result.difference
    if result.p_value >= ALPHA:
        verdict = "no significant difference"
    elif diff.mean > 0:
        verdict = "significant improvement"
    else:
        verdict = "significant regression"

    print(f"{args.metric} on {diff.n} paired questions")
    print(f"  baseline   {result.mean_a:.3f}")
    print(f"  candidate  {result.mean_b:.3f}")
    print(
        f"  difference {diff.mean:+.3f} ({diff.confidence:.0%} interval {diff.low:+.3f} to "
        f"{diff.high:+.3f})"
    )
    print(f"  p-value    {result.p_value:.4f} (paired permutation test)")
    print(f"  verdict    {verdict} at alpha {ALPHA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
