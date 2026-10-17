"""Writing, reading, summarising and comparing eval runs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from copilot.eval.report import (
    RunSummary,
    compare_family,
    compare_runs,
    read_rows,
    read_summary,
    summarise,
    summarise_by,
    write_run,
)


def _rows(scores: list[float]) -> list[dict[str, Any]]:
    kinds = ("metrics-generated", "novel-generated")
    return [
        {"id": f"q{i:03d}", "question_type": kinds[i % 2], "hit@10": score}
        for i, score in enumerate(scores)
    ]


def _write(directory: Path, scores: list[float], split: str = "dev", run: str = "r") -> Path:
    rows = _rows(scores)
    summary = RunSummary(
        suite="retrieval",
        run=run,
        split=split,
        created=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        questions=len(rows),
        test_split_opened=split == "test",
        system={"baseline": "test"},
        metrics=summarise(rows, ["hit@10"]),
        by={"question_type": summarise_by(rows, ["hit@10"], "question_type")},
    )
    write_run(directory, summary, rows)
    return directory


def test_a_run_round_trips(tmp_path: Path) -> None:
    directory = _write(tmp_path / "run", [1.0, 0.0, 1.0, 1.0])

    assert read_rows(directory) == _rows([1.0, 0.0, 1.0, 1.0])
    summary = read_summary(directory)
    assert summary.metrics["hit@10"].mean == pytest.approx(0.75)
    assert summary.by["question_type"]["metrics-generated"].questions == 2


def test_markdown_summary_lists_metrics_and_groups(tmp_path: Path) -> None:
    directory = _write(tmp_path / "run", [1.0, 0.0, 1.0, 1.0], split="test")

    markdown = (directory / "summary.md").read_text(encoding="utf-8")
    assert markdown.startswith("# retrieval: r (test)\n")
    assert "| hit@10 | 0.750 |" in markdown
    assert "## By question type" in markdown
    assert "held-out test split was opened" in markdown


def test_compare_runs_pairs_questions_by_id(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 20)
    candidate = _write(tmp_path / "b", [1.0] * 15 + [0.0] * 5)

    result = compare_runs(baseline, candidate, "hit@10")

    assert result.difference.mean == pytest.approx(0.75)
    assert result.p_value < 0.001


def test_compare_runs_refuses_different_questions(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 20)
    candidate = _write(tmp_path / "b", [1.0] * 19)

    with pytest.raises(ValueError, match="different questions"):
        compare_runs(baseline, candidate, "hit@10")


def test_compare_runs_refuses_different_splits(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 20)
    candidate = _write(tmp_path / "b", [1.0] * 20, split="test")

    with pytest.raises(ValueError, match="different splits"):
        compare_runs(baseline, candidate, "hit@10")


def test_compare_family_adjusts_p_values_across_candidates(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 20)
    strong = _write(tmp_path / "b", [1.0] * 15 + [0.0] * 5, run="strong")
    weak = _write(tmp_path / "c", [1.0] * 3 + [0.0] * 17, run="weak")

    results = compare_family(baseline, [strong, weak], "hit@10")

    assert [r.run for r in results] == ["strong", "weak"]
    assert results[0].adjusted_p == pytest.approx(min(1.0, 2 * results[0].comparison.p_value))
    assert results[1].adjusted_p >= results[1].comparison.p_value
    assert results[0].adjusted_p < 0.05 < results[1].adjusted_p
