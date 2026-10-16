"""Score a router on the routing eval set and write a run to eval/results/routing/.

Usage:
  uv run poe eval-routing --baseline keyword                  # the floor to beat
  uv run poe eval-routing --baseline majority
  uv run poe eval-routing --predictions routes.jsonl --run llm-router-v1
  uv run poe eval-routing ... --split test --allow-test       # milestone evaluations only
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from copilot.eval import routing
from copilot.eval.report import (
    RESULTS_DIR,
    RunSummary,
    render_markdown,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import HeldOutError

METRICS = ["accuracy"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--baseline", choices=("keyword", "majority"))
    source.add_argument("--predictions", type=Path, help='JSON Lines of {"id", "route"}')
    parser.add_argument("--run", help="run name (defaults to the baseline or file name)")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    try:
        queries = routing.load_queries(args.split, allow_test=args.allow_test)
    except HeldOutError:
        print("The routing test split is held out. Add --allow-test only for a milestone run.")
        return 2

    if args.baseline == "keyword":
        predictions: dict[str, str] = {q.id: routing.keyword_route(q.query) for q in queries}
        system = {"baseline": "keyword"}
    elif args.baseline == "majority":
        route = routing.majority_route(routing.load_queries("dev"))
        predictions = {q.id: route for q in queries}
        system = {"baseline": "majority", "route": route}
    else:
        predictions = routing.read_predictions(args.predictions)
        system = {"predictions": args.predictions.name}
    run = args.run or args.baseline or args.predictions.stem

    rows = routing.score(queries, predictions)
    summary = RunSummary(
        suite="routing",
        run=run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system=system,
        metrics=summarise(rows, METRICS),
        by={
            "route": summarise_by(rows, METRICS, "route"),
            "origin": summarise_by(rows, METRICS, "origin"),
        },
    )
    directory = args.results_dir / "routing" / run / args.split
    write_run(directory, summary, rows)
    print(render_markdown(summary))
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
