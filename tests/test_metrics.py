"""Per-question retrieval metrics."""

from __future__ import annotations

import pytest

from copilot.eval.metrics import distinct, hit_at_k, recall_at_k, reciprocal_rank

RANKED = ["p3", "p1", "p3", "p7", "p2", "p9"]


def test_distinct_keeps_first_positions() -> None:
    assert distinct(RANKED) == ["p3", "p1", "p7", "p2", "p9"]


@pytest.mark.parametrize(
    ("relevant", "k", "expected"),
    [
        ({"p1"}, 1, 0.0),
        ({"p1"}, 2, 1.0),
        ({"p1", "p2"}, 3, 0.5),
        ({"p1", "p2"}, 4, 1.0),
        ({"p8"}, 10, 0.0),
    ],
)
def test_recall_at_k_counts_distinct_items(relevant: set[str], k: int, expected: float) -> None:
    assert recall_at_k(RANKED, relevant, k) == expected


def test_hit_at_k_needs_only_one_relevant_item() -> None:
    assert hit_at_k(RANKED, {"p2", "p8"}, 4) == 1.0
    assert hit_at_k(RANKED, {"p2", "p8"}, 3) == 0.0


@pytest.mark.parametrize(
    ("relevant", "k", "expected"),
    [
        ({"p3"}, 10, 1.0),
        ({"p7", "p2"}, 10, 1 / 3),
        ({"p9"}, 4, 0.0),
        ({"p8"}, 10, 0.0),
    ],
)
def test_reciprocal_rank_uses_the_first_relevant_item(
    relevant: set[str], k: int, expected: float
) -> None:
    assert reciprocal_rank(RANKED, relevant, k) == pytest.approx(expected)


def test_empty_ranking_scores_zero() -> None:
    assert recall_at_k([], {"p1"}, 5) == hit_at_k([], {"p1"}, 5) == reciprocal_rank([], {"p1"}, 5)
    assert recall_at_k([], {"p1"}, 5) == 0.0


def test_a_question_without_relevant_items_is_an_error() -> None:
    with pytest.raises(ValueError, match="relevant"):
        recall_at_k(RANKED, set(), 5)


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        hit_at_k(RANKED, {"p1"}, 0)
