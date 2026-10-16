"""Per-question metrics. Each returns one number for one question; `stats` aggregates them.

Ranked lists are de-duplicated first (the first occurrence wins), so "top k" always means
the first k distinct items. That matters when chunks are mapped to pages: three chunks from
one page count once.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable, Sequence


def distinct[T: Hashable](ranked: Sequence[T]) -> list[T]:
    """The ranked items with repeats removed, keeping each item's first position."""
    return list(dict.fromkeys(ranked))


def recall_at_k[T: Hashable](ranked: Sequence[T], relevant: Collection[T], k: int) -> float:
    """The share of relevant items that appear in the top k."""
    gold = _gold(relevant, k)
    return len(gold.intersection(distinct(ranked)[:k])) / len(gold)


def hit_at_k[T: Hashable](ranked: Sequence[T], relevant: Collection[T], k: int) -> float:
    """1.0 if at least one relevant item appears in the top k, else 0.0."""
    gold = _gold(relevant, k)
    return 1.0 if gold.intersection(distinct(ranked)[:k]) else 0.0


def reciprocal_rank[T: Hashable](ranked: Sequence[T], relevant: Collection[T], k: int) -> float:
    """1 / the rank of the first relevant item in the top k, or 0.0 if there is none."""
    gold = _gold(relevant, k)
    for rank, item in enumerate(distinct(ranked)[:k], start=1):
        if item in gold:
            return 1.0 / rank
    return 0.0


def _gold[T: Hashable](relevant: Collection[T], k: int) -> set[T]:
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}.")
    if not relevant:
        raise ValueError("A question needs at least one relevant item to be scored.")
    return set(relevant)
