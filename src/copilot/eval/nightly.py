"""The nightly evaluation (step 9.1, ADR-0034): its steps, what it keeps, and when a night
counts as a regression.

Each night the copilot answers a fixed slice of FinanceBench's dev questions (all of them
on Sundays), its answers are judged and checked against their sources, the LLM router
decides the routing set's dev questions, and the data agent answers the SQL set's. Each
step is one of the evaluation scripts, run in a process of its own under the night's
spending cap (`copilot.llm.budget`): a step may spend until the night's ledger reaches its
share of the cap, so a step that spends less leaves the rest to the steps after it.

A night keeps metrics only: for each question its id, its categories, its scores, its cost
and its time, never a question or an answer, since FinanceBench's licence keeps those out
of the public history. It is compared with the last full run on the questions both
answered, metric by metric, by a paired permutation test, and the night's tests are
adjusted together (Holm): a significant drop is a regression.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from copilot.eval.labels import stratified_sample
from copilot.eval.stats import bootstrap_ci, exact_interval, holm, paired_test
from copilot.llm.budget import RunBudget

# 32 questions: a measured night of 40 (11 November) cost $0.378 of its $0.40 cap, too
# close to it; 32 leave about a fifth of the cap for nights that cost more (ADR-0034)
SLICE_SIZE = 32
SLICE_SEED = 20261111
ALPHA = 0.05
# The metrics a night is tested on: per question, 1 or 0
TESTED = ("correct", "answered", "routing_accuracy", "sql_accuracy")
# Routes whose answers cite filing pages, so the faithfulness check can read them
CITING_ROUTES = ("doc", "hybrid")
# A Python traceback's last line starts with the exception's class
_EXCEPTION = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception))\b")


def choose_slice(
    rows: Sequence[Mapping[str, Any]], size: int = SLICE_SIZE, seed: int = SLICE_SEED
) -> list[str]:
    """`size` ids from a full run's rows, in proportion to each route and question type,
    kept in the rows' order."""
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(f"{row['route']}/{row['question_type']}", []).append(str(row["id"]))
    chosen = stratified_sample(groups, size, seed)
    return [str(row["id"]) for row in rows if row["id"] in chosen]


@dataclass(frozen=True, slots=True)
class Step:
    """An evaluation script, and the share of the night's cap the ledger may reach before
    it stops (counted from the start of the night)."""

    name: str
    share: float
    script: str
    args: tuple[str, ...]


def steps(run: str, results_dir: Path, ids_file: Path | None = None) -> list[Step]:
    """The night's steps in order. Answers come first and get the largest share."""
    results = ("--results-dir", str(results_dir))
    ids = ("--ids", str(ids_file)) if ids_file is not None else ()
    routing = ("--router", "llm", "--role", "strong", "--run", f"{run}-routing")
    return [
        Step("answers", 0.50, "scripts/run_copilot.py", ("--run", run, *ids, *results)),
        Step("judge", 0.57, "scripts/judge_answers.py", ("--run", run, *results)),
        Step("faithfulness", 0.65, "scripts/check_faithfulness.py", ("--run", run, *results)),
        Step("routing", 0.82, "scripts/run_router.py", (*routing, *results)),
        Step("sql", 1.0, "scripts/run_sql_agent.py", ("--run", f"{run}-sql", *results)),
    ]


def failure(log: Path) -> str:
    """The class of the exception that ended a step, from its log. Never the message, which
    could quote a question."""
    for line in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()):
        if match := _EXCEPTION.match(line.strip()):
            return match.group(1)
    return "no exception in the log"


def run_steps(
    night: Sequence[Step], budget_usd: float, ledger: Path, logs: Path, cwd: Path
) -> list[dict[str, Any]]:
    """Run each step in its own process under its share of the cap, with its output in
    `logs/<step>.log`, and say how each ended: finished, stopped by its cap, or failed."""
    logs.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for step in night:
        cap = round(budget_usd * step.share, 4)
        env = os.environ | {
            "FRC_LLM_BUDGET_USD": str(cap),
            "FRC_LLM_BUDGET_FILE": str(ledger),
            "PYTHONIOENCODING": "utf-8",
        }
        log = logs / f"{step.name}.log"
        began = time.perf_counter()
        with log.open("w", encoding="utf-8") as output:
            code = subprocess.run(
                [sys.executable, step.script, *step.args],
                cwd=cwd,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        spent = RunBudget(ledger, cap).spent()
        stopped = code != 0 and spent >= cap
        outcome: dict[str, Any] = {
            "step": step.name,
            "exit": code,
            "cap_usd": cap,
            "spent_usd": round(spent, 4),
            "stopped_by_cap": stopped,
            "failed": code != 0 and not stopped,
            "seconds": round(time.perf_counter() - began, 1),
        }
        if outcome["failed"]:
            outcome["error"] = failure(log)
        outcomes.append(outcome)
    return outcomes


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a line cut short by a kill
    return rows


def _items(results_dir: Path, suite: str, run: str) -> dict[str, dict[str, Any]]:
    """A finished step's per-question rows by id; empty when the step didn't finish.
    A judge's run is named after the answers run and the judge (`<run>--<judge>`)."""
    judged = sorted((results_dir / suite).glob(f"{run}--*/dev/items.jsonl"))
    for path in [*judged, results_dir / suite / run / "dev" / "items.jsonl"]:
        if path.exists():
            return {row["id"]: row for row in _jsonl(path)}
    return {}


def copilot_rows(
    answers_file: Path, results_dir: Path, run: str, ids: Sequence[str]
) -> list[dict[str, Any]]:
    """The copilot's metrics per question, in `ids`' order, for the questions it answered.

    Its answers file is read rather than its summary, which only a finished run writes, so
    a night cut short by its cap still counts what it answered. Only ids, categories and
    numbers are kept."""
    answers = {row["id"]: row for row in _jsonl(answers_file)}
    judged = _items(results_dir, "correctness", run)
    checked = _items(results_dir, "faithfulness", run)
    rows = []
    for question_id in ids:
        answer = answers.get(question_id)
        if answer is None:
            continue
        verdict, check = judged.get(question_id), checked.get(question_id)
        cites = answer.get("route") in CITING_ROUTES and answer.get("answerable")
        rows.append(
            {
                "id": question_id,
                "question_type": answer["question_type"],
                "route": answer.get("route", ""),
                "answered": float(bool(answer.get("answerable"))),
                "correct": None if verdict is None else float(verdict["correct"]),
                "faithful": float(check["faithful"]) if cites and check is not None else None,
                "revised": float(answer.get("revisions", 0) > 0),
                "handed_on": float(answer.get("handoff") is not None),
                "cost_usd": round(float(answer.get("cost_usd") or 0.0), 6),
                "seconds": float(answer.get("seconds", 0.0)),
            }
        )
    return rows


def set_rows(results_dir: Path, suite: str, run: str, keep: Sequence[str]) -> list[dict[str, Any]]:
    """A finished routing or SQL step's rows: the id, the score and the fields in `keep`.
    Both sets are the project's own, so their routes and categories may be published."""
    return [
        {"id": row["id"], "accuracy": float(row["accuracy"])} | {key: row.get(key) for key in keep}
        for row in _items(results_dir, suite, run).values()
    ]


def _mean(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, float] | None:
    """The mean with its 95% interval: the bootstrap's, or the exact binomial one when a
    share of 1s and 0s reaches 0 or 1, where the bootstrap collapses (ADR-0007)."""
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    interval = bootstrap_ci(values)
    low, high = interval.low, interval.high
    if set(values) <= {0.0, 1.0} and (low <= 0.0 or high >= 1.0):
        low, high = exact_interval(round(sum(values)), len(values))
    return {"mean": interval.mean, "low": low, "high": high, "n": len(values)}


def summary(
    copilot: Sequence[Mapping[str, Any]],
    routing: Sequence[Mapping[str, Any]],
    sql: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The night's headline numbers, each with its 95% interval and the questions behind it."""
    seconds = sorted(float(row["seconds"]) for row in copilot)
    return {
        "correct": _mean(copilot, "correct"),
        "answered": _mean(copilot, "answered"),
        "faithful": _mean(copilot, "faithful"),
        "routing_accuracy": _mean(routing, "accuracy"),
        "sql_accuracy": _mean(sql, "accuracy"),
        "cost_per_question": (
            round(statistics.fmean(row["cost_usd"] for row in copilot), 6) if copilot else None
        ),
        "median_seconds": round(statistics.median(seconds), 2) if seconds else None,
        "p95_seconds": (
            round(seconds[min(len(seconds) - 1, int(0.95 * len(seconds)))], 2) if seconds else None
        ),
    }


def scores(night: Mapping[str, Any], metric: str) -> dict[str, float]:
    """One tested metric of a stored night, by question id."""
    part, key = {
        "correct": ("copilot", "correct"),
        "answered": ("copilot", "answered"),
        "routing_accuracy": ("routing", "accuracy"),
        "sql_accuracy": ("sql", "accuracy"),
    }[metric]
    return {row["id"]: float(row[key]) for row in night.get(part, []) if row.get(key) is not None}


def compare(night: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Each tested metric against the baseline on the questions both have, Holm-adjusted
    across the night's tests; a significant drop is a regression."""
    tests: list[dict[str, Any]] = []
    for metric in TESTED:
        now, before = scores(night, metric), scores(baseline, metric)
        shared = [question_id for question_id in before if question_id in now]
        if not shared:
            continue
        result = paired_test([before[i] for i in shared], [now[i] for i in shared])
        tests.append(
            {
                "metric": metric,
                "questions": len(shared),
                "baseline": round(result.mean_a, 4),
                "night": round(result.mean_b, 4),
                "difference": round(result.difference.mean, 4),
                "low": round(result.difference.low, 4),
                "high": round(result.difference.high, 4),
                "p": result.p_value,
            }
        )
    for test, adjusted in zip(tests, holm([test["p"] for test in tests]), strict=True):
        test["p_holm"] = adjusted
        test["regression"] = adjusted < ALPHA and test["difference"] < 0
    return tests


def history_line(night: Mapping[str, Any]) -> dict[str, Any]:
    """What the trend keeps of a night: everything but the per-question rows."""
    return {key: value for key, value in night.items() if key not in ("copilot", "routing", "sql")}
