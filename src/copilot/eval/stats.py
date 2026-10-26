"""Uncertainty and significance for evaluation results (ADR-0007).

- `bootstrap_ci`: a percentile bootstrap interval for the mean of per-question scores.
- `paired_test`: compares two systems on the same questions. It reports the mean
  difference with a paired bootstrap interval, and a two-sided p-value from a paired
  permutation (sign-flip) test.
- `mcnemar_exact`: the exact McNemar test for two systems' right-or-wrong outcomes.
- `holm`: Holm-Bonferroni adjusted p-values for several comparisons made at once.
- `exact_interval`: the Clopper-Pearson interval for a share of right answers, for when a
  bootstrap interval collapses against 0 or 1.
- `cohens_kappa` and `kappa_interval`: agreement between two raters (a judge and a person)
  beyond what chance would give, with a bootstrap interval.

Every resampling function takes a seed, so the same scores always give the same numbers.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

CONFIDENCE = 0.95
RESAMPLES = 10_000

# Floating-point slack when comparing permuted statistics with the observed one, so exact
# ties (common with 0/1 scores) count as ties.
_TIE_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class Interval:
    mean: float
    low: float
    high: float
    n: int
    confidence: float


@dataclass(frozen=True, slots=True)
class PairedComparison:
    """System B against system A on the same questions; `difference` is B minus A."""

    mean_a: float
    mean_b: float
    difference: Interval
    p_value: float


def bootstrap_ci(
    values: Sequence[float],
    *,
    confidence: float = CONFIDENCE,
    resamples: int = RESAMPLES,
    seed: int = 0,
) -> Interval:
    """The mean of `values` with a percentile bootstrap confidence interval.

    Resample the questions with replacement, recompute the mean each time, and take the
    middle `confidence` share of those means.
    """
    scores = _as_scores(values)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, scores.size, size=(resamples, scores.size))
    means = scores[picks].mean(axis=1)
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return Interval(
        mean=float(scores.mean()),
        low=float(low),
        high=float(high),
        n=int(scores.size),
        confidence=confidence,
    )


def paired_test(
    a: Sequence[float],
    b: Sequence[float],
    *,
    confidence: float = CONFIDENCE,
    resamples: int = RESAMPLES,
    seed: int = 0,
) -> PairedComparison:
    """Compare system B with system A question by question.

    Under the null hypothesis the two systems are interchangeable, so each per-question
    difference is as likely to be positive as negative. The p-value is the share of random
    sign flips whose mean difference is at least as far from zero as the observed one,
    with the observed arrangement counted once.
    """
    scores_a, scores_b = _as_scores(a), _as_scores(b)
    if scores_a.size != scores_b.size:
        raise ValueError(
            f"Paired scores need equal lengths, got {scores_a.size} and {scores_b.size}."
        )
    differences = scores_b - scores_a
    observed = abs(float(differences.mean()))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(resamples, differences.size))
    flipped = np.abs((signs * differences).mean(axis=1))
    as_extreme = int(np.count_nonzero(flipped >= observed - _TIE_TOLERANCE))
    return PairedComparison(
        mean_a=float(scores_a.mean()),
        mean_b=float(scores_b.mean()),
        difference=bootstrap_ci(
            differences.tolist(), confidence=confidence, resamples=resamples, seed=seed + 1
        ),
        p_value=(as_extreme + 1) / (resamples + 1),
    )


def mcnemar_exact(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Two-sided exact McNemar p-value for two systems' right-or-wrong outcomes.

    Only the questions where exactly one system is right carry information; under the null
    hypothesis each of them is equally likely to favour either system.
    """
    if len(a) != len(b):
        raise ValueError(f"Paired outcomes need equal lengths, got {len(a)} and {len(b)}.")
    only_a = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    only_b = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    discordant = only_a + only_b
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(only_a, only_b) + 1))
    return min(1.0, 2 * tail / (1 << discordant))


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order.

    The smallest p-value is multiplied by the number of comparisons, the next by one fewer,
    and so on; each adjusted value is at least as large as the one before it.
    """
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for position, index in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - position) * p_values[index]))
        adjusted[index] = running
    return adjusted


def exact_interval(right: int, total: int, confidence: float = CONFIDENCE) -> tuple[float, float]:
    """The Clopper-Pearson interval for `right` successes in `total` trials.

    Each bound is the proportion at which the observed count sits exactly in one tail of the
    binomial distribution, found by bisection. When every answer is right the lower bound is
    ((1 - confidence) / 2) ** (1 / total), as a bootstrap interval can't show.
    """
    if not 0 <= right <= total or total == 0:
        raise ValueError(f"Need 0 <= right <= total and total > 0, got {right} of {total}.")
    tail = (1 - confidence) / 2

    def at_least(p: float) -> float:  # P(X >= right)
        return sum(
            math.comb(total, k) * p**k * (1 - p) ** (total - k) for k in range(right, total + 1)
        )

    def at_most(p: float) -> float:  # P(X <= right)
        return sum(math.comb(total, k) * p**k * (1 - p) ** (total - k) for k in range(right + 1))

    def solve(tail_of: Callable[[float], float], rising: bool) -> float:
        low, high = 0.0, 1.0
        for _ in range(100):
            middle = (low + high) / 2
            if (tail_of(middle) < tail) == rising:
                low = middle
            else:
                high = middle
        return (low + high) / 2

    lower = 0.0 if right == 0 else solve(at_least, rising=True)
    upper = 1.0 if right == total else solve(at_most, rising=False)
    return lower, upper


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Agreement between two raters beyond chance: 1 is perfect, 0 is what chance gives.

    NaN when both raters gave every item the same one label: chance agreement is then
    already perfect, and kappa is undefined.
    """
    codes_a, codes_b = _label_codes(a, b)
    return float(_kappas(codes_a[np.newaxis, :], codes_b[np.newaxis, :])[0])


def kappa_interval(
    a: Sequence[str],
    b: Sequence[str],
    *,
    confidence: float = CONFIDENCE,
    resamples: int = RESAMPLES,
    seed: int = 0,
) -> Interval:
    """Cohen's kappa with a percentile bootstrap interval, resampling the rated items.

    Resamples where kappa is undefined are left out of the interval.
    """
    codes_a, codes_b = _label_codes(a, b)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, codes_a.size, size=(resamples, codes_a.size))
    kappas = _kappas(codes_a[picks], codes_b[picks])
    tail = (1.0 - confidence) / 2.0
    low, high = np.nanquantile(kappas, [tail, 1.0 - tail])
    return Interval(
        mean=cohens_kappa(a, b),
        low=float(low),
        high=float(high),
        n=int(codes_a.size),
        confidence=confidence,
    )


def _label_codes(a: Sequence[str], b: Sequence[str]) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    if len(a) != len(b) or not a:
        raise ValueError(f"Two raters need the same non-empty items, got {len(a)} and {len(b)}.")
    labels = {label: code for code, label in enumerate(sorted(set(a) | set(b)))}
    return (
        np.array([labels[x] for x in a], dtype=np.int64),
        np.array([labels[y] for y in b], dtype=np.int64),
    )


def _kappas(a: NDArray[np.int64], b: NDArray[np.int64]) -> NDArray[np.float64]:
    """Kappa for each row of two equally shaped label-code matrices."""
    observed = (a == b).mean(axis=1)
    expected = np.zeros(a.shape[0])
    for code in np.union1d(a, b):
        expected += (a == code).mean(axis=1) * (b == code).mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        kappas = (observed - expected) / (1.0 - expected)
    return np.where(np.isclose(expected, 1.0), np.nan, kappas)


def _as_scores(values: Sequence[float]) -> NDArray[np.float64]:
    scores = np.asarray(values, dtype=np.float64)
    if scores.ndim != 1 or scores.size == 0:
        raise ValueError("Scores must be a non-empty list of numbers.")
    if not np.all(np.isfinite(scores)):
        raise ValueError("Scores must be finite numbers.")
    return scores
