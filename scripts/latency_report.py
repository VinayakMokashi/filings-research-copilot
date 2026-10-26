"""Latency and cost of the copilot's runs, from their trace files (step 6.5).

  uv run poe latency-report                                  # the API's runs
  uv run poe latency-report data/traces/copilot-v1.jsonl     # the end-to-end evaluation's

Prints the median, 95th percentile and slowest run by route, and each node's times, and
writes them as JSON to eval/results/latency/<trace name>.json. No model calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from copilot.eval.latency import read_events, read_runs, summarise, table

RESULTS = Path("eval/results/latency")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("traces", nargs="*", type=Path, default=[Path("data/traces/api.jsonl")])
    parser.add_argument("--out", type=Path, help="where to write the JSON summary")
    args = parser.parse_args()
    summary = summarise(read_runs(read_events(args.traces)))
    summary["traces"] = [path.as_posix() for path in args.traces]
    out = args.out or RESULTS / f"{args.traces[0].stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{summary['runs']} complete runs\n")
    print(table(summary))
    print(f"\nWritten to {out.as_posix()}")


if __name__ == "__main__":
    main()
