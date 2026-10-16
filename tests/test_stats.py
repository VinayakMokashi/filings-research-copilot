"""Bootstrap intervals, paired tests and multiple-comparison adjustment."""

from __future__ import annotations

import math

import pytest

from copilot.eval.stats import bootstrap_ci, holm, mcnemar_exact, paired_test

SCORES = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0] * 5  # mean 0.7, n = 50


def test_bootstrap_interval_brackets_the_mean() -> None:
    interval = bootstrap_ci(SCORES)

    assert interval.mean == pytest.approx(0.7)
    assert interval.low < 0.7 < interval.high
    assert interval.n == 50
    assert interval.confidence == 0.95


def test_bootstrap_matches_the_normal_approximation_roughly() -> None:
    interval = bootstrap_ci(SCORES, resamples=20_000)
    half_width = 1.96 * math.sqrt(0.7 * 0.3 / 50)

    assert (interval.high - interval.low) / 2 == pytest.approx(half_width, rel=0.15)


def test_bootstrap_is_reproducible_with_a_seed() -> None:
    graded = [((i * 37) % 101) / 101 for i in range(60)]

    assert bootstrap_ci(graded, seed=7) == bootstrap_ci(graded, seed=7)
    assert bootstrap_ci(graded, seed=7) != bootstrap_ci(graded, seed=8)


def test_more_questions_narrow_the_interval() -> None:
    small, large = bootstrap_ci(SCORES[:20]), bootstrap_ci(SCORES * 4)

    assert large.high - large.low < small.high - small.low


def test_constant_scores_have_no_uncertainty() -> None:
    interval = bootstrap_ci([0.5] * 10)

    assert (interval.low, interval.mean, interval.high) == (0.5, 0.5, 0.5)


@pytest.mark.parametrize("bad", [[], [float("nan")], [float("inf"), 1.0]])
def test_bootstrap_rejects_bad_scores(bad: list[float]) -> None:
    with pytest.raises(ValueError, match="Scores"):
        bootstrap_ci(bad)


def test_identical_systems_are_not_significantly_different() -> None:
    result = paired_test(SCORES, SCORES)

    assert result.difference.mean == 0.0
    assert result.p_value == 1.0


def test_a_consistent_improvement_is_significant() -> None:
    baseline = [0.0] * 30
    better = [1.0] * 20 + [0.0] * 10

    result = paired_test(baseline, better, resamples=5_000)

    assert result.difference.mean == pytest.approx(2 / 3)
    assert result.difference.low > 0
    assert result.p_value == pytest.approx(1 / 5_001)


def test_a_small_noisy_difference_is_not_significant() -> None:
    a = [1.0, 0.0] * 20
    b = [1.0, 0.0] * 19 + [1.0, 1.0]

    result = paired_test(a, b)

    assert result.difference.mean == pytest.approx(1 / 40)
    assert result.p_value > 0.5


def test_paired_scores_must_line_up() -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        paired_test([1.0, 0.0], [1.0])


@pytest.mark.parametrize(
    ("only_a", "only_b", "expected"),
    [
        (0, 0, 1.0),
        (0, 6, 2 / 64),
        (3, 3, 1.0),
        (1, 9, 2 * (1 + 10) / 1024),
    ],
)
def test_mcnemar_exact(only_a: int, only_b: int, expected: float) -> None:
    both = 5
    a = [True] * only_a + [False] * only_b + [True] * both
    b = [False] * only_a + [True] * only_b + [True] * both

    assert mcnemar_exact(a, b) == pytest.approx(expected)


def test_holm_adjusts_in_input_order() -> None:
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])
    assert holm([]) == []
