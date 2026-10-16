"""Score SQL predictions on the SQL eval set and write a run to eval/results/sql/.

Usage:
  uv run poe eval-sql --baseline gold                      # gold SQL, declining the rest: 100%
  uv run poe eval-sql --baseline decline-all               # the floor for declining
  uv run poe eval-sql --predictions answers.jsonl --run sql-agent-v1
  uv run poe eval-sql ... --split test --allow-test        # milestone evaluations only
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import sql
from copilot.eval.report import (
    RESULTS_DIR,
    RunSummary,
    render_markdown,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import HeldOutError
from copilot.facts.database import connect_read_only

METRICS = ["accuracy"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--baseline", choices=("gold", "decline-all"))
    source.add_argument(
        "--predictions", type=Path, help='JSON Lines of {"id", "sql"} or {"id", "declined"}'
    )
    parser.add_argument("--run", help="run name (defaults to the baseline or file name)")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    try:
        questions = sql.load_questions(args.split, allow_test=args.allow_test)
    except HeldOutError:
        print("The SQL test split is held out. Add --allow-test only for a milestone run.")
        return 2

    if args.baseline == "gold":
        predictions = {
            q.id: sql.Prediction(id=q.id, sql=q.gold_sql, declined=not q.answerable)
            for q in questions
        }
        system = {"baseline": "gold"}
    elif args.baseline == "decline-all":
        predictions = {q.id: sql.Prediction(id=q.id, declined=True) for q in questions}
        system = {"baseline": "decline-all"}
    else:
        predictions = sql.read_predictions(args.predictions)
        system = {"predictions": args.predictions.name}
    run = args.run or args.baseline or args.predictions.stem

    conn = connect_read_only(get_settings().data_dir / "processed" / "facts.db")
    try:
        rows = sql.score(questions, predictions, conn)
    finally:
        conn.close()
    summary = RunSummary(
        suite="sql",
        run=run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system=system,
        metrics=summarise(rows, METRICS),
        by={
            "answerable": summarise_by(rows, METRICS, "answerable"),
            "difficulty": summarise_by(rows, METRICS, "difficulty"),
        },
    )
    directory = args.results_dir / "sql" / run / args.split
    write_run(directory, summary, rows)
    print(render_markdown(summary))
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
