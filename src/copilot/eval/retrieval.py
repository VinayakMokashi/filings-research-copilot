"""Scoring retrieval against FinanceBench's evidence pages.

A prediction is a ranked list of pages for each question, and a page is relevant when it
is one of the question's evidence pages (a document plus a 0-based page index). Scores:

- `recall@k`: the share of the question's evidence pages found in the top k;
- `hit@k`: whether at least one evidence page is in the top k;
- `mrr@10`: 1 / the rank of the first evidence page in the top 10.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from copilot.eval.financebench import Question, read_jsonl
from copilot.eval.metrics import distinct, hit_at_k, recall_at_k, reciprocal_rank

KS = (5, 10, 20)
MRR_K = 10


class PageRef(NamedTuple):
    doc_name: str
    page: int


class _PredictedPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_name: str
    page: int = Field(ge=0)


class _Prediction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    pages: list[_PredictedPage]


def gold_pages(question: Question) -> frozenset[PageRef]:
    return frozenset(PageRef(e.doc_name, e.page) for e in question.evidence)


def metric_names(ks: Sequence[int] = KS) -> list[str]:
    return [*(f"recall@{k}" for k in ks), *(f"hit@{k}" for k in ks), f"mrr@{MRR_K}"]


def score(
    questions: Sequence[Question],
    predictions: Mapping[str, Sequence[PageRef]],
    ks: Sequence[int] = KS,
) -> list[dict[str, Any]]:
    """One row per question with every retrieval metric and the top pages retrieved.

    Predictions must cover exactly the given questions: a missing question would otherwise
    score as a silent zero.
    """
    expected = {question.id for question in questions}
    missing, extra = expected - predictions.keys(), predictions.keys() - expected
    if missing or extra:
        raise ValueError(
            f"Predictions don't match the questions: {len(missing)} missing, {len(extra)} extra."
        )
    rows = []
    for question in questions:
        ranked = list(predictions[question.id])
        gold = gold_pages(question)
        row: dict[str, Any] = {"id": question.id, "question_type": question.question_type}
        row |= {f"recall@{k}": recall_at_k(ranked, gold, k) for k in ks}
        row |= {f"hit@{k}": hit_at_k(ranked, gold, k) for k in ks}
        row[f"mrr@{MRR_K}"] = reciprocal_rank(ranked, gold, MRR_K)
        row["retrieved"] = [[page.doc_name, page.page] for page in distinct(ranked)[: max(ks)]]
        rows.append(row)
    return rows


def first_pages(questions: Sequence[Question], k: int = max(KS)) -> dict[str, list[PageRef]]:
    """A floor to beat: the first k pages of the question's own document."""
    return {q.id: [PageRef(q.doc_name, page) for page in range(k)] for q in questions}


def read_predictions(path: Path) -> dict[str, list[PageRef]]:
    """Predictions as JSON Lines: `{"id": ..., "pages": [{"doc_name": ..., "page": ...}]}`.

    Pages are 0-based and ranked best first.
    """
    predictions: dict[str, list[PageRef]] = {}
    for record in read_jsonl(path):
        prediction = _Prediction.model_validate(record)
        if prediction.id in predictions:
            raise ValueError(f"{path} predicts {prediction.id} more than once.")
        predictions[prediction.id] = [PageRef(p.doc_name, p.page) for p in prediction.pages]
    return predictions
