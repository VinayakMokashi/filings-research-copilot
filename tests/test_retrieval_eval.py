"""Scoring retrieval predictions against FinanceBench evidence pages."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from copilot.eval import retrieval
from copilot.eval.financebench import Question
from copilot.eval.retrieval import PageRef

RecordFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def questions(question_record: RecordFactory) -> list[Question]:
    two_pages = question_record(2, doc_name="BOLT_2022_10K", page=40)
    two_pages["evidence"].append(dict(two_pages["evidence"][0], evidence_page_num=41))
    return [
        Question.model_validate(question_record(1, doc_name="ACME_2022_10K", page=3)),
        Question.model_validate(two_pages),
    ]


def test_gold_pages_cover_every_evidence_passage(questions: list[Question]) -> None:
    assert retrieval.gold_pages(questions[1]) == {
        PageRef("BOLT_2022_10K", 40),
        PageRef("BOLT_2022_10K", 41),
    }


def test_score_reports_each_metric_per_question(questions: list[Question]) -> None:
    predictions = {
        "financebench_id_00001": [PageRef("ACME_2022_10K", 9), PageRef("ACME_2022_10K", 3)],
        "financebench_id_00002": [
            PageRef("BOLT_2022_10K", 41),
            *(PageRef("OTHER_2022_10K", p) for p in range(30)),
        ],
    }

    first, second = retrieval.score(questions, predictions)

    assert (first["hit@5"], first["recall@5"], first["mrr@10"]) == (1.0, 1.0, 0.5)
    assert (second["hit@5"], second["recall@5"], second["mrr@10"]) == (1.0, 0.5, 1.0)
    assert len(second["retrieved"]) == 20
    assert first["question_type"] == "metrics-generated"


def test_predictions_must_cover_exactly_the_questions(questions: list[Question]) -> None:
    with pytest.raises(ValueError, match="1 missing, 0 extra"):
        retrieval.score(questions, {"financebench_id_00001": []})


def test_first_pages_baseline_ranks_the_opening_pages(questions: list[Question]) -> None:
    predictions = retrieval.first_pages(questions, k=5)

    rows = retrieval.score(questions, predictions)
    assert predictions["financebench_id_00001"][0] == PageRef("ACME_2022_10K", 0)
    assert rows[0]["hit@5"] == 1.0  # evidence on page index 3
    assert rows[1]["hit@20"] == 0.0  # evidence on page indexes 40 and 41


def test_read_predictions(tmp_path: Path) -> None:
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        json.dumps({"id": "q1", "pages": [{"doc_name": "ACME_2022_10K", "page": 3}]}) + "\n",
        encoding="utf-8",
    )

    assert retrieval.read_predictions(path) == {"q1": [PageRef("ACME_2022_10K", 3)]}


def test_read_predictions_rejects_duplicates(tmp_path: Path) -> None:
    line = json.dumps({"id": "q1", "pages": []}) + "\n"
    path = tmp_path / "predictions.jsonl"
    path.write_text(line * 2, encoding="utf-8")

    with pytest.raises(ValueError, match="more than once"):
        retrieval.read_predictions(path)
