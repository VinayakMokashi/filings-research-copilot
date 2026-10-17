"""Eval run records: per-question rows, a summary with confidence intervals, and comparisons.

A run directory holds three files:

- `items.jsonl`: one row per question, with its id, every metric and the prediction;
- `summary.json`: what ran, on which split, and each metric's mean with its interval;
- `summary.md`: the same summary as tables, for reading on GitHub.

Rows hold question ids and predictions only, never benchmark text.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from copilot.eval.stats import (
    CONFIDENCE,
    RESAMPLES,
    PairedComparison,
    bootstrap_ci,
    holm,
    paired_test,
)

RESULTS_DIR = Path("eval/results")


class MetricSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mean: float
    low: float
    high: float


class GroupSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    questions: int
    metrics: dict[str, MetricSummary]


class RunSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suite: str
    run: str
    split: str
    created: datetime
    questions: int
    test_split_opened: bool
    system: dict[str, Any] = Field(default_factory=dict)
    confidence: float = CONFIDENCE
    resamples: int = RESAMPLES
    metrics: dict[str, MetricSummary]
    by: dict[str, dict[str, GroupSummary]] = Field(default_factory=dict)


def summarise(
    rows: Sequence[Mapping[str, Any]], metrics: Sequence[str], *, seed: int = 0
) -> dict[str, MetricSummary]:
    """Each metric's mean over the rows, with a bootstrap interval."""
    summaries = {}
    for name in metrics:
        interval = bootstrap_ci([float(row[name]) for row in rows], seed=seed)
        summaries[name] = MetricSummary(mean=interval.mean, low=interval.low, high=interval.high)
    return summaries


def summarise_by(
    rows: Sequence[Mapping[str, Any]], metrics: Sequence[str], key: str, *, seed: int = 0
) -> dict[str, GroupSummary]:
    """`summarise` within each value of `key` (for example each question type)."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {
        group: GroupSummary(questions=len(members), metrics=summarise(members, metrics, seed=seed))
        for group, members in sorted(groups.items())
    }


def write_run(directory: Path, summary: RunSummary, rows: Sequence[Mapping[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "items.jsonl").open("w", encoding="utf-8", newline="\n") as items:
        for row in rows:
            items.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (directory / "summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (directory / "summary.md").write_text(render_markdown(summary), encoding="utf-8", newline="\n")


def read_rows(directory: Path) -> list[dict[str, Any]]:
    with (directory / "items.jsonl").open(encoding="utf-8") as items:
        return [json.loads(line) for line in items if line.strip()]


def read_summary(directory: Path) -> RunSummary:
    return RunSummary.model_validate_json((directory / "summary.json").read_text(encoding="utf-8"))


def render_markdown(summary: RunSummary) -> str:
    level = f"{summary.confidence:.0%}"
    header = (
        f"{summary.questions} questions, {level} bootstrap intervals "
        f"({summary.resamples:,} resamples), {summary.created:%Y-%m-%d %H:%M} UTC"
    )
    if summary.test_split_opened:
        header += ". The held-out test split was opened for this run."
    lines = [
        f"# {summary.suite}: {summary.run} ({summary.split})",
        "",
        header,
        "",
        f"| Metric | Mean | {level} interval |",
        "|---|---|---|",
        *(
            f"| {name} | {m.mean:.3f} | {m.low:.3f} to {m.high:.3f} |"
            for name, m in summary.metrics.items()
        ),
    ]
    names = list(summary.metrics)
    for key, groups in summary.by.items():
        label = key.replace("_", " ")
        lines += [
            "",
            f"## By {label}",
            "",
            f"| {label.capitalize()} | Questions | " + " | ".join(names) + " |",
            "|---" * (len(names) + 2) + "|",
        ]
        for group, result in groups.items():
            cells = (
                f"{result.metrics[n].mean:.3f} ({result.metrics[n].low:.2f} to "
                f"{result.metrics[n].high:.2f})"
                for n in names
            )
            lines.append(f"| {group} | {result.questions} | " + " | ".join(cells) + " |")
    if summary.system:
        system = json.dumps(summary.system, indent=2, sort_keys=True)
        lines += ["", "## System", "", "```json", system, "```"]
    return "\n".join(lines) + "\n"


def compare_runs(
    baseline: Path, candidate: Path, metric: str, *, seed: int = 0
) -> PairedComparison:
    """A paired test of `candidate` against `baseline` on one metric, matched by question id."""
    splits = {read_summary(baseline).split, read_summary(candidate).split}
    if len(splits) > 1:
        raise ValueError(f"The runs are on different splits: {', '.join(sorted(splits))}.")
    a = {row["id"]: float(row[metric]) for row in read_rows(baseline)}
    b = {row["id"]: float(row[metric]) for row in read_rows(candidate)}
    if a.keys() != b.keys():
        raise ValueError(
            f"The runs cover different questions: {len(a.keys() - b.keys())} only in the "
            f"baseline, {len(b.keys() - a.keys())} only in the candidate."
        )
    ids = sorted(a)
    return paired_test([a[i] for i in ids], [b[i] for i in ids], seed=seed)


@dataclass(frozen=True, slots=True)
class FamilyResult:
    """One candidate's paired comparison with the baseline, and its Holm-adjusted p-value."""

    run: str
    comparison: PairedComparison
    adjusted_p: float


def compare_family(
    baseline: Path, candidates: Sequence[Path], metric: str, *, seed: int = 0
) -> list[FamilyResult]:
    """`compare_runs` for each candidate, with p-values adjusted across the family (Holm)."""
    comparisons = [compare_runs(baseline, candidate, metric, seed=seed) for candidate in candidates]
    adjusted = holm([comparison.p_value for comparison in comparisons])
    return [
        FamilyResult(read_summary(candidate).run, comparison, p)
        for candidate, comparison, p in zip(candidates, comparisons, adjusted, strict=True)
    ]
