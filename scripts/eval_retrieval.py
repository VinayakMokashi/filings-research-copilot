"""Score retrieval on FinanceBench evidence pages and write a run to eval/results/retrieval/.

Usage:
  uv run poe eval-retrieval --baseline first-pages             # the floor to beat
  uv run poe eval-retrieval --predictions preds.jsonl --run hybrid-v1
  uv run poe eval-retrieval ... --split test --allow-test      # milestone evaluations only
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import retrieval
from copilot.eval.report import (
    RESULTS_DIR,
    RunSummary,
    render_markdown,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import HeldOutError, load_split
from copilot.logs import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--baseline", choices=("first-pages",), help="score a built-in baseline")
    source.add_argument("--predictions", type=Path, help="JSON Lines file of ranked pages")
    parser.add_argument("--run", help="run name (defaults to the baseline or file name)")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "raw" / "financebench"
    try:
        questions = load_split(args.split, root, allow_test=args.allow_test)
    except HeldOutError:
        print(
            "The test split is held out for milestone evaluations (ADR-0006). "
            "Add --allow-test only for one of those."
        )
        return 2

    if args.baseline:
        predictions = retrieval.first_pages(questions)
        system = {"baseline": args.baseline, "pages": max(retrieval.KS), "document": "oracle"}
        run = args.run or args.baseline
    else:
        predictions = retrieval.read_predictions(args.predictions)
        system = {"predictions": args.predictions.name}
        run = args.run or args.predictions.stem

    rows = retrieval.score(questions, predictions)
    names = retrieval.metric_names()
    summary = RunSummary(
        suite="retrieval",
        run=run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system=system,
        metrics=summarise(rows, names),
        by={"question_type": summarise_by(rows, names, "question_type")},
    )
    directory = args.results_dir / "retrieval" / run / args.split
    write_run(directory, summary, rows)
    print(render_markdown(summary))
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
