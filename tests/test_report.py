"""Writing, reading, summarising and comparing eval runs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from copilot.eval.report import (
    MetricSummary,
    RunSummary,
    compare_family,
    compare_runs,
    outcome_table,
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


def test_a_run_level_metric_gets_no_column_in_the_group_tables(tmp_path: Path) -> None:
    rows = _rows([1.0, 0.0, 1.0, 1.0])
    metrics = summarise(rows, ["hit@10"])
    metrics["cohens_kappa"] = MetricSummary(mean=0.8, low=0.6, high=1.0)
    summary = RunSummary(
        suite="judge-agreement",
        run="r",
        split="dev",
        created=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
        questions=len(rows),
        test_split_opened=False,
        metrics=metrics,
        by={"question_type": summarise_by(rows, ["hit@10"], "question_type")},
    )

    write_run(tmp_path / "run", summary, rows)

    markdown = (tmp_path / "run" / "summary.md").read_text(encoding="utf-8")
    assert "| cohens_kappa | 0.800 |" in markdown
    assert "| Question type | Questions | hit@10 |" in markdown


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


def test_compare_runs_can_keep_one_question_type(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 40)
    rows = [row | {"hit@10": 1.0} for row in _rows([0.0] * 40)[::2]]  # metrics-generated only
    summary = RunSummary(
        suite="retrieval",
        run="b",
        split="dev",
        created=datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
        questions=len(rows),
        test_split_opened=False,
        metrics=summarise(rows, ["hit@10"]),
    )
    write_run(tmp_path / "b", summary, rows)
    metrics = {"question_type": "metrics-generated"}

    with pytest.raises(ValueError, match="different questions"):
        compare_runs(baseline, tmp_path / "b", "hit@10")
    result = compare_runs(baseline, tmp_path / "b", "hit@10", where=metrics)

    assert result.difference.n == 20
    assert result.difference.mean == pytest.approx(1.0)
    with pytest.raises(ValueError, match="No questions"):
        compare_runs(baseline, tmp_path / "b", "hit@10", where={"question_type": "other"})


def test_outcome_table_counts_who_gets_each_question(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [1.0, 1.0, 0.0, 0.0, 1.0])
    candidate = _write(tmp_path / "b", [1.0, 0.0, 1.0, 0.0, 1.0])

    table = outcome_table(baseline, candidate, "hit@10")

    assert table == {"both": 2, "baseline only": 1, "candidate only": 1, "neither": 1}
    graded = _write(tmp_path / "c", [0.5, 0.0, 1.0, 0.0, 1.0])
    assert outcome_table(baseline, graded, "hit@10") is None


def test_compare_family_adjusts_p_values_across_candidates(tmp_path: Path) -> None:
    baseline = _write(tmp_path / "a", [0.0] * 20)
    strong = _write(tmp_path / "b", [1.0] * 15 + [0.0] * 5, run="strong")
    weak = _write(tmp_path / "c", [1.0] * 3 + [0.0] * 17, run="weak")

    results = compare_family(baseline, [strong, weak], "hit@10")

    assert [r.run for r in results] == ["strong", "weak"]
    assert results[0].adjusted_p == pytest.approx(min(1.0, 2 * results[0].comparison.p_value))
    assert results[1].adjusted_p >= results[1].comparison.p_value
    assert results[0].adjusted_p < 0.05 < results[1].adjusted_p
