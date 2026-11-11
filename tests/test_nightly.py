"""The nightly evaluation: its slice and steps, what a night keeps, and its regression test."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from copilot.eval.nightly import (
    Step,
    choose_slice,
    compare,
    copilot_rows,
    history_line,
    run_steps,
    set_rows,
    steps,
    summary,
)

ALLOWED = {"id", "question_type", "route", "answered", "correct", "faithful", "revised"}
ALLOWED |= {"handed_on", "cost_usd", "seconds"}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_the_slice_keeps_each_route_and_question_type_in_proportion() -> None:
    rows = [
        {"id": f"q{n:03d}", "route": route, "question_type": kind}
        for n, (route, kind) in enumerate(
            [("data", "metrics")] * 40 + [("doc", "novel")] * 40 + [("hybrid", "domain")] * 20
        )
    ]

    chosen = choose_slice(rows, size=40, seed=1)

    picked = Counter(row["route"] for row in rows if row["id"] in chosen)
    assert picked == {"data": 16, "doc": 16, "hybrid": 8}
    assert chosen == sorted(chosen)  # in the rows' order
    assert choose_slice(rows, size=40, seed=1) == chosen  # the same every time


def test_each_step_may_reach_more_of_the_cap_and_answers_take_the_slice(tmp_path: Path) -> None:
    night = steps("nightly-2026-11-12-slice", tmp_path / "results", tmp_path / "slice.json")
    shares = [step.share for step in night]

    assert [step.name for step in night] == ["answers", "judge", "faithfulness", "routing", "sql"]
    assert shares == sorted(shares)
    assert shares[-1] == 1.0
    assert "--ids" in night[0].args
    assert "--ids" not in steps("nightly-full", tmp_path)[0].args
    assert night[3].args[:4] == ("--router", "llm", "--role", "strong")  # as deployed


def test_a_night_keeps_ids_categories_and_scores_only(tmp_path: Path) -> None:
    run, results = "nightly-2026-11-12-slice", tmp_path / "results"
    answers = tmp_path / "answers.jsonl"
    write_jsonl(
        answers,
        [
            {"id": "a", "question_type": "novel-generated", "route": "doc", "answerable": True,
             "text": "Revenue rose [1].", "sources": [{"text": "a filing page"}],
             "revisions": 1, "handoff": None, "cost_usd": 0.004, "seconds": 3.5},
            {"id": "b", "question_type": "metrics-generated", "route": "data", "answerable": True,
             "text": "$1,577 million.", "revisions": 0, "handoff": None, "cost_usd": 0.003,
             "seconds": 2.0},
            {"id": "c", "question_type": "domain-relevant", "route": "doc", "answerable": False,
             "text": "", "revisions": 0, "handoff": None, "cost_usd": 0.002, "seconds": 9.0},
        ],
    )  # fmt: skip
    judged = results / "correctness" / f"{run}--qwen-3.8-27b-p2" / "dev" / "items.jsonl"
    write_jsonl(judged, [{"id": "a", "correct": 1.0}, {"id": "b", "correct": 0.0}])
    checked = results / "faithfulness" / f"{run}--qwen-3.8-27b-f1" / "dev" / "items.jsonl"
    write_jsonl(checked, [{"id": "a", "faithful": 1.0}, {"id": "b", "faithful": 0.0}])

    rows = copilot_rows(answers, results, run, ["a", "b", "c", "d"])

    assert [row["id"] for row in rows] == ["a", "b", "c"]  # d was never answered
    assert all(set(row) <= ALLOWED for row in rows)  # no question, answer or source text
    assert [row["correct"] for row in rows] == [1.0, 0.0, None]
    assert [row["faithful"] for row in rows] == [1.0, None, None]  # data answers cite no page
    assert rows[0]["revised"] == 1.0
    assert rows[2]["answered"] == 0.0


def test_a_finished_set_keeps_its_scores_and_the_fields_asked_for(tmp_path: Path) -> None:
    items = tmp_path / "routing" / "n-routing" / "dev" / "items.jsonl"
    write_jsonl(items, [{"id": "r001", "accuracy": 1.0, "route": "doc", "reason": "..."}])

    rows = set_rows(tmp_path, "routing", "n-routing", ("route",))

    assert rows == [{"id": "r001", "accuracy": 1.0, "route": "doc"}]
    assert set_rows(tmp_path, "sql", "n-sql", ("category",)) == []  # the step didn't finish


def test_the_summary_gives_each_metric_with_its_interval() -> None:
    copilot = [
        {"correct": float(n % 2), "answered": 1.0, "faithful": None, "cost_usd": 0.005,
         "seconds": float(n)}
        for n in range(1, 21)
    ]  # fmt: skip

    night = summary(copilot, [{"accuracy": 1.0}], [])

    assert night["correct"]["mean"] == 0.5
    assert night["correct"]["n"] == 20
    assert night["correct"]["low"] < 0.5 < night["correct"]["high"]
    assert night["faithful"] is None
    assert night["sql_accuracy"] is None
    assert night["cost_per_question"] == 0.005
    assert (night["median_seconds"], night["p95_seconds"]) == (10.5, 20.0)


def test_a_share_at_one_gets_the_exact_interval() -> None:
    night = summary([], [{"accuracy": 1.0}] * 138, [{"accuracy": 1.0}] * 27 + [{"accuracy": 0.0}])

    routing, sql = night["routing_accuracy"], night["sql_accuracy"]
    assert routing["mean"] == 1.0
    assert routing["high"] == 1.0
    assert 0.97 < routing["low"] < 0.98  # Clopper-Pearson for 138 of 138
    assert sql["high"] < 1.0  # 27 of 28: the bootstrap would reach 1.0
    assert night["correct"] is None


def night_of(correct: list[float]) -> dict[str, Any]:
    return {
        "run": "n",
        "copilot": [
            {"id": f"q{n}", "correct": value, "answered": 1.0} for n, value in enumerate(correct)
        ],
        "routing": [{"id": f"r{n}", "accuracy": 1.0} for n in range(10)],
        "sql": [],
    }


def test_a_large_drop_is_a_regression_and_an_unchanged_night_is_not() -> None:
    baseline = night_of([1.0] * 30 + [0.0] * 10)

    unchanged = compare(night_of([1.0] * 30 + [0.0] * 10), baseline)
    dropped = compare(night_of([0.0] * 12 + [1.0] * 18 + [0.0] * 10), baseline)

    assert [test["metric"] for test in unchanged] == ["correct", "answered", "routing_accuracy"]
    assert not any(test["regression"] for test in unchanged)
    correct = dropped[0]
    assert correct["difference"] == -0.3
    assert correct["questions"] == 40
    assert correct["p_holm"] >= correct["p"]
    assert correct["regression"]


def test_a_rise_is_never_a_regression() -> None:
    better = compare(night_of([1.0] * 40), night_of([0.0] * 20 + [1.0] * 20))

    assert better[0]["difference"] == 0.5
    assert not better[0]["regression"]


def test_the_history_line_leaves_out_every_question() -> None:
    line = history_line(night_of([1.0]) | {"summary": {"correct": None}, "partial": False})

    assert set(line) == {"run", "summary", "partial"}


def script(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_each_step_runs_under_its_share_and_a_failure_keeps_its_message_out(
    tmp_path: Path,
) -> None:
    spend = (
        "import json, os\n"
        "with open(os.environ['FRC_LLM_BUDGET_FILE'], 'a') as f:\n"
        "    f.write(json.dumps({'usd': float(os.environ['FRC_LLM_BUDGET_USD'])}) + '\\n')\n"
        "print('a question the log must keep to itself')\n"
        "raise SystemExit(1)\n"
    )
    crash = "raise ValueError('What was the capital expenditure of a company in 2018?')\n"
    night = [
        Step("answers", 0.5, script(tmp_path, "answers", spend), ()),
        Step("judge", 0.8, script(tmp_path, "judge", "print('fine')\n"), ()),
        Step("routing", 1.0, script(tmp_path, "routing", crash), ()),
    ]

    outcomes = run_steps(night, 0.40, tmp_path / "ledger.jsonl", tmp_path / "logs", tmp_path)

    answers, judge, routing = outcomes
    assert answers["stopped_by_cap"]
    assert not answers["failed"]
    assert answers["cap_usd"] == 0.2
    assert answers["spent_usd"] == 0.2
    assert (judge["exit"], judge["failed"], judge["stopped_by_cap"]) == (0, False, False)
    assert routing["failed"]
    assert routing["error"] == "ValueError"
    assert "capital expenditure" not in json.dumps(outcomes)
    assert "must keep" in (tmp_path / "logs" / "answers.log").read_text(encoding="utf-8")
