"""The answer bandit online, against its randomized fixed arm (step 9.3, ADR-0036).

The report reads the bandit's log, one record per answer an arm wrote (`bandit-answers` in
Firestore), and compares the policy's group with the control's: answers a coin flip sent
to the policy or to the fixed arm, on the same traffic and provider. Each kind of reward is
compared on its own:

- `canary judge`: the faithfulness judge on the canary's answers, every one of them;
- `visitor judge`: the judge on the sample of visitors' answers it scored;
- `visitor thumbs`: visitors' ratings.

Each comparison gives both groups' mean rewards with bootstrap intervals, the difference
(policy minus control) with its interval, and a permutation test's p-value. A second
answer (`retry`) is counted apart and compared with nothing.

The decision follows ADR-0036's rule, set before the data: the bandit stays on only if the
policy's mean reward on the canary's judged answers is at least the control's. When the
difference's interval spans zero, the report says the two can't be told apart.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from statistics import fmean
from typing import Any

from copilot.eval.stats import bootstrap_ci, two_sample_test

GROUPS = ("policy", "control")
DECIDES = "canary judge"


def _reward(record: Mapping[str, Any], kind: str) -> float | None:
    if kind == "canary judge":
        return record.get("judge") if record.get("canary") else None
    if kind == "visitor judge":
        return None if record.get("canary") else record.get("judge")
    return None if record.get("canary") else record.get("thumbs")


def _when(record: Mapping[str, Any]) -> datetime | None:
    created = record.get("created")
    if isinstance(created, datetime):
        return created
    return datetime.fromisoformat(str(created)) if created else None


def within(
    records: Iterable[Mapping[str, Any]], since: datetime | None, until: datetime | None
) -> list[Mapping[str, Any]]:
    """The records created in [since, until)."""
    kept = []
    for record in records:
        when = _when(record)
        if when is None or (since and when < since) or (until and when >= until):
            continue
        kept.append(record)
    return kept


def _mean(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    interval = bootstrap_ci(values)
    return {"mean": interval.mean, "low": interval.low, "high": interval.high, "n": len(values)}


def compare(policy: list[float], control: list[float]) -> dict[str, Any]:
    """Both groups' mean rewards, and the policy's minus the control's when both have some."""
    found: dict[str, Any] = {"policy": _mean(policy), "control": _mean(control)}
    if policy and control:
        test = two_sample_test(control, policy)
        found["difference"] = {
            "mean": test.difference.mean,
            "low": test.difference.low,
            "high": test.difference.high,
            "p": test.p_value,
        }
    return found


def report(
    records: Iterable[Mapping[str, Any]],
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """The comparison of the bandit's two groups, and ADR-0036's decision."""
    period = within(records, since, until)
    grouped = {group: [r for r in period if r.get("assignment") == group] for group in GROUPS}
    comparisons = {
        kind: compare(
            [float(v) for r in grouped["policy"] if (v := _reward(r, kind)) is not None],
            [float(v) for r in grouped["control"] if (v := _reward(r, kind)) is not None],
        )
        for kind in ("canary judge", "visitor judge", "visitor thumbs")
    }
    difference = comparisons[DECIDES].get("difference")
    keep = told_apart = False
    if difference is not None:
        keep = difference["mean"] >= 0
        told_apart = difference["low"] > 0 or difference["high"] < 0
    decision = {
        "rule": (
            "Keep the bandit on only if the policy's mean reward on the canary's judged "
            "answers is at least the control's (ADR-0036)."
        ),
        "keep": keep,
        "told_apart": told_apart,
    }
    costs = {
        group: round(fmean(costs), 6)
        if (costs := [float(r["cost_usd"]) for r in rows if r.get("cost_usd") is not None])
        else None
        for group, rows in grouped.items()
    }
    return {
        "since": since.isoformat() if since else None,
        "until": until.isoformat() if until else None,
        "answers": {group: len(rows) for group, rows in grouped.items()},
        "canary_answers": {
            group: sum(bool(r.get("canary")) for r in rows) for group, rows in grouped.items()
        },
        "retries": sum(r.get("assignment") == "retry" for r in period),
        "arms": {
            group: dict(Counter(str(r.get("arm")) for r in rows)) for group, rows in grouped.items()
        },
        "cost_per_answer_usd": costs,
        "comparisons": comparisons,
        "decision": decision,
    }
