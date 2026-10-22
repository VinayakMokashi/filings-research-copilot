"""Choosing answers to label by hand, and reading the labels back."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from copilot.eval.labels import allocate, labellers, read_labels, stratified_sample


def test_allocate_is_proportional_and_adds_up() -> None:
    shares = allocate({"domain": 30, "metrics": 30, "novel": 25}, 40)

    assert sum(shares.values()) == 40
    assert shares == {"domain": 14, "metrics": 14, "novel": 12}
    with pytest.raises(ValueError, match="only 3 are available"):
        allocate({"a": 3}, 4)


def test_stratified_sample_is_repeatable_and_stratified() -> None:
    groups = {"a": [f"a{i}" for i in range(20)], "b": [f"b{i}" for i in range(10)]}

    sample = stratified_sample(groups, 9, seed=1)

    assert sample == stratified_sample(groups, 9, seed=1)
    assert Counter(item[0] for item in sample) == {"a": 6, "b": 3}


def test_read_labels_keeps_decided_labels_for_one_run(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    rows = [
        {"id": "q1", "answers_run": "v3", "label": "correct"},
        {"id": "q2", "answers_run": "v3", "label": "unsure"},
        {"id": "q3", "answers_run": "v2", "label": "incorrect"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n\n", encoding="utf-8")

    assert read_labels(path, "v3") == {"q1": "correct"}
    assert labellers(path, "v3") == ["unknown"]
    path.write_text(json.dumps({"id": "q4", "answers_run": "v3", "label": "maybe"}))
    with pytest.raises(ValueError, match="Unknown label"):
        read_labels(path, "v3")
