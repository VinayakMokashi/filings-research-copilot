"""Run the nightly evaluation (step 9.1, ADR-0034) and keep its metrics.

Runs each step of `copilot.eval.nightly.steps` as a process of its own, under the night's
spending cap, then writes metrics only to --out:

- `night.json`: per question its id, categories and scores; the night's summary; what it
  cost, by model; and, with --baseline (the last full run's night.json), each tested
  metric against it;
- `history.json`: the same without the per-question rows, the line the trend keeps.

Each step's own output goes to `<out>/logs/<step>.log` and stays on the machine that ran
it: a step can print what a question asked, and a CI log is public.

Exit codes: 0 when the night was measured, even if the cap stopped a step (it is then
`partial`); 2 when a step failed for another reason; 3 on a regression.

Usage (the models come from the run's environment, as in ADR-0024's evaluations):
  uv run poe nightly-eval --set slice --budget 0.40 --out dist/nightly/2026-11-12
  uv run poe nightly-eval --set full --budget 1.20 --out DIR --baseline last-full/night.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.nightly import (
    compare,
    copilot_rows,
    history_line,
    run_steps,
    set_rows,
    steps,
    summary,
)
from copilot.eval.splits import load_split
from copilot.llm.budget import RunBudget, spent_by_model
from copilot.llm.gateway import role_models

ROOT = Path(__file__).resolve().parents[1]
SLICE_FILE = ROOT / "eval" / "nightly" / "slice.json"
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def commit() -> str:
    if sha := os.environ.get("GITHUB_SHA"):
        return sha
    found = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return found.stdout.strip() or "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--set", choices=("slice", "full"), required=True)
    parser.add_argument("--budget", type=float, required=True, help="the night's cap, dollars")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="the last full run's night.json")
    parser.add_argument("--date", default=datetime.now(IST).date().isoformat())
    parser.add_argument("--slice", type=Path, default=SLICE_FILE)
    args = parser.parse_args(argv)

    settings = get_settings()
    run = f"nightly-{args.date}-{args.set}"
    out = args.out.resolve()
    ledger, results = out / "ledger.jsonl", out / "results"
    if args.set == "slice":
        ids = json.loads(args.slice.read_text(encoding="utf-8"))["ids"]
        ids_file: Path | None = args.slice.resolve()
    else:
        questions = load_split("dev", settings.data_dir / "raw" / "financebench")
        ids, ids_file = [question.id for question in questions], None

    started = datetime.now(UTC)
    outcomes = run_steps(steps(run, results, ids_file), args.budget, ledger, out / "logs", ROOT)
    for o in outcomes:
        note = " (stopped by its cap)" if o["stopped_by_cap"] else f" ({o.get('error')})"
        print(
            f"{o['step']}: exit {o['exit']} in {o['seconds']} s, ${o['spent_usd']:.4f} of the "
            f"night spent, cap ${o['cap_usd']:.4f}{note if o['exit'] else ''}"
        )

    answers_file = settings.data_dir / "processed" / "answers" / run / "dev" / "answers.jsonl"
    copilot = copilot_rows(answers_file, results, run, ids)
    routing = set_rows(results, "routing", f"{run}-routing", ("route", "predicted", "origin"))
    sql = set_rows(results, "sql", f"{run}-sql", ("category", "difficulty", "answerable"))
    cut_short = any(o["stopped_by_cap"] or o["failed"] for o in outcomes)
    night: dict[str, Any] = {
        "date": args.date,
        "set": args.set,
        "run": run,
        "commit": commit(),
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": role_models(settings),
        "budget_usd": args.budget,
        "spent_usd": round(RunBudget(ledger, args.budget).spent(), 4),
        "spent_by_model": {model: round(usd, 4) for model, usd in spent_by_model(ledger).items()},
        "questions": len(ids),
        "partial": cut_short or len(copilot) < len(ids),
        "steps": outcomes,
        "summary": summary(copilot, routing, sql),
        "tests": [],
        "regression": None,
        "copilot": copilot,
        "routing": routing,
        "sql": sql,
    }
    if args.baseline is not None and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        night["baseline"] = baseline["run"]
        if not night["partial"]:  # a night cut short draws no verdict (ADR-0034)
            night["tests"] = compare(night, baseline)
            night["regression"] = any(test["regression"] for test in night["tests"])
    (out / "night.json").write_text(
        json.dumps(night, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "history.json").write_text(
        json.dumps(history_line(night)) + "\n", encoding="utf-8", newline="\n"
    )

    headline = {
        name: round(value["mean"], 3)
        for name, value in night["summary"].items()
        if isinstance(value, dict)
    }
    print(f"{run}: {headline}; ${night['spent_usd']:.4f} of ${args.budget:.2f}")
    print(f"partial={night['partial']} regression={night['regression']}; wrote {out}")
    if night["regression"]:
        return 3
    return 2 if any(o["failed"] for o in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
