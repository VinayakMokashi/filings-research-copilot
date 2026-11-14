"""The online bandit's report: randomized groups, kinds of reward, the decision (ADR-0036)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from copilot.eval.bandit_online import report, within
from copilot.eval.stats import two_sample_test

DAY = datetime(2026, 11, 20, 10, tzinfo=UTC)


def record(group: str, *, judge: float | None = None, **fields: Any) -> dict[str, Any]:
    return {
        "created": DAY.isoformat(),
        "arm": "strong" if group == "control" else "fast",
        "assignment": group,
        "canary": True,
        "judge": judge,
        "cost_usd": 0.005,
    } | fields


def test_two_independent_groups_are_compared_by_relabelling() -> None:
    same = two_sample_test([1.0, 0.0] * 20, [1.0, 0.0] * 20)
    apart = two_sample_test([0.0] * 30, [1.0] * 30)

    assert same.difference.mean == 0.0
    assert same.p_value > 0.9
    assert apart.difference.mean == 1.0
    assert apart.p_value < 0.001
    assert apart.difference.low == pytest.approx(1.0)


def test_the_decision_keeps_a_policy_that_earns_at_least_the_controls() -> None:
    records = [record("policy", judge=1.0)] * 9 + [record("policy", judge=0.0)]
    records += [record("control", judge=1.0)] * 8 + [record("control", judge=0.0)] * 2

    found = report(records)

    canary = found["comparisons"]["canary judge"]
    assert canary["policy"]["mean"] == pytest.approx(0.9)
    assert canary["control"]["mean"] == pytest.approx(0.8)
    assert canary["difference"]["mean"] == pytest.approx(0.1)
    assert found["decision"]["keep"] is True
    assert found["decision"]["told_apart"] is False  # ten answers a group can't tell
    assert found["answers"] == {"policy": 10, "control": 10}
    assert found["arms"] == {"policy": {"fast": 10}, "control": {"strong": 10}}


def test_a_policy_that_earns_less_is_switched_off_and_without_data_nothing_is_kept() -> None:
    worse = [record("policy", judge=0.0)] * 5 + [record("control", judge=1.0)] * 5

    assert report(worse)["decision"]["keep"] is False
    assert report([])["decision"]["keep"] is False  # nothing to compare: the rule isn't met


def test_kinds_of_reward_are_kept_apart_and_retries_counted_alone() -> None:
    records = [
        record("policy", judge=1.0),
        record("control", judge=0.0, canary=False),  # a visitor's judged answer
        record("control", canary=False, thumbs=1.0),
        record("retry", judge=None, canary=False, thumbs=0.0),
    ]

    found = report(records)

    assert found["comparisons"]["canary judge"]["control"] is None
    assert found["comparisons"]["visitor judge"]["control"]["mean"] == 0.0
    assert found["comparisons"]["visitor thumbs"]["control"]["mean"] == 1.0
    assert "difference" not in found["comparisons"]["visitor thumbs"]
    assert found["retries"] == 1
    assert found["cost_per_answer_usd"] == {"policy": 0.005, "control": 0.005}


def test_the_period_is_since_inclusive_and_until_exclusive() -> None:
    early = record("policy", judge=1.0, created="2026-11-15T23:59:00+00:00")
    first = record("policy", judge=1.0, created="2026-11-16T00:00:00+00:00")
    late = record("policy", judge=1.0, created=datetime(2026, 11, 30, tzinfo=UTC))

    kept = within(
        [early, first, late],
        datetime(2026, 11, 16, tzinfo=UTC),
        datetime(2026, 11, 30, tzinfo=UTC),
    )

    assert kept == [first]


def script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_script_writes_numbers_only(tmp_path: Path) -> None:
    main = script("bandit_report").main

    log = tmp_path / "log.jsonl"
    rows = [record("policy", judge=1.0), record("control", judge=0.0)]
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    assert main(["--from", str(log), "--name", "trial", "--results-dir", str(tmp_path)]) == 0

    summary = json.loads((tmp_path / "bandit-online" / "trial" / "summary.json").read_text())
    assert summary["answers"] == {"policy": 1, "control": 1}
    assert summary["decision"]["keep"] is True
