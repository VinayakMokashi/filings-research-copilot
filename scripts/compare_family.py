"""Compare several candidate runs with one baseline on one metric, Holm-adjusted (ADR-0007).

Each candidate gets a paired permutation test against the baseline; the p-values are then
adjusted together, so the chance of any false win in the family stays at alpha.

Usage:
  uv run poe compare-family BASELINE_DIR CANDIDATE_DIR [CANDIDATE_DIR ...] --metric recall@10
  uv run poe compare-family ... --out eval/results/retrieval/_comparisons/chunking
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from copilot.eval.report import compare_family, read_summary

ALPHA = 0.05


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("baseline", type=Path, help="run directory of the current baseline")
    parser.add_argument("candidates", type=Path, nargs="+", help="run directories to compare")
    parser.add_argument("--metric", required=True, help="a metric name from items.jsonl")
    parser.add_argument("--title", default="Comparison", help="heading for the written report")
    parser.add_argument("--out", type=Path, help="write <out>.md and <out>.json")
    args = parser.parse_args(argv)

    base = read_summary(args.baseline)
    results = compare_family(args.baseline, args.candidates, args.metric)
    rows = []
    for result in results:
        diff = result.comparison.difference
        if result.adjusted_p >= ALPHA:
            verdict = "no significant difference"
        elif diff.mean > 0:
            verdict = "better"
        else:
            verdict = "worse"
        rows.append(
            {
                "run": result.run,
                "baseline": round(result.comparison.mean_a, 4),
                "candidate": round(result.comparison.mean_b, 4),
                "difference": round(diff.mean, 4),
                "low": round(diff.low, 4),
                "high": round(diff.high, 4),
                "p": round(result.comparison.p_value, 4),
                "holm_p": round(result.adjusted_p, 4),
                "verdict": verdict,
            }
        )

    n = results[0].comparison.difference.n if results else 0
    lines = [
        f"# {args.title}",
        "",
        f"{args.metric} on {n} paired {base.split} questions against the baseline "
        f"`{base.run}`; paired permutation tests, Holm-adjusted across {len(rows)} "
        f"comparisons, alpha {ALPHA}.",
        "",
        "| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |",
        "|---|---|---|---|---|---|---|",
        *[
            f"| `{r['run']}` | {r['baseline']:.3f} | {r['candidate']:.3f} | "
            f"{r['difference']:+.3f} ({r['low']:+.3f} to {r['high']:+.3f}) | "
            f"{r['p']:.4f} | {r['holm_p']:.4f} | {r['verdict']} |"
            for r in rows
        ],
        "",
    ]
    report = "\n".join(lines)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".md").write_text(report, encoding="utf-8", newline="\n")
        record = {"metric": args.metric, "baseline": base.run, "alpha": ALPHA, "rows": rows}
        args.out.with_suffix(".json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
