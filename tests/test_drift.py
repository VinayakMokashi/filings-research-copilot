"""Drift checks (step 9.5): the windows, the paired and distribution tests, the flags."""

from __future__ import annotations

from typing import Any

import pytest

from copilot.eval.drift import canary_drift, ks_test, nightly_drift, per_question


def night(date: str, *, similarity: float | None = None, refused: int = 0) -> dict[str, Any]:
    """A night of 20 questions; the first `refused` went unanswered."""
    return {
        "date": date,
        "copilot": [
            {
                "id": f"q{n:02d}",
                "answered": 0.0 if n < refused else 1.0,
                "similarity": None if similarity is None else similarity + n / 1000,
            }
            for n in range(20)
        ],
    }


def day(date: str, seconds: float, ids: range = range(10)) -> dict[str, Any]:
    return {
        "date": date,
        "rows": [
            {"id": f"r{n:03d}", "ok": True, "seconds": seconds + n / 10, "similarity": 0.8}
            for n in ids
        ],
    }


def test_the_ks_statistic_is_the_largest_gap_between_the_two_distributions() -> None:
    same, p_same = ks_test([0.1, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, 0.4], resamples=500)
    apart, p_apart = ks_test([0.1 * n for n in range(10)], [5 + 0.1 * n for n in range(10)])

    assert (same, apart) == (0.0, 1.0)
    assert p_same == 1.0
    assert p_apart < 0.001
    with pytest.raises(ValueError, match="need values"):
        ks_test([], [1.0])


def test_too_few_nights_compare_nothing() -> None:
    report = nightly_drift([night(f"2026-11-1{n}", similarity=0.8) for n in range(5)])

    assert report["checks"] == {}
    assert report["periods"] == {}


def test_a_signal_starts_from_the_first_nights_that_recorded_it() -> None:
    nights = [night(f"2026-11-0{n}") for n in range(1, 4)]  # before similarity was recorded
    nights += [night(f"2026-11-1{n}", similarity=0.8) for n in range(6)]

    report = nightly_drift(nights)

    assert report["periods"]["similarity"]["reference"] == [
        "2026-11-10",
        "2026-11-11",
        "2026-11-12",
    ]
    assert report["periods"]["refusals"]["reference"] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    similarity = report["checks"]["similarity"]
    assert similarity["questions"] == 20
    assert similarity["difference"] == 0.0
    assert similarity["drift"] is False
    assert report["checks"]["similarity_distribution"]["ks"] == 0.0


def test_a_changed_collection_shows_as_drift_in_similarity() -> None:
    nights = [night(f"2026-11-1{n}", similarity=0.80) for n in range(3)]
    nights += [night(f"2026-11-2{n}", similarity=0.65) for n in range(3)]

    checks = nightly_drift(nights)["checks"]

    assert checks["similarity"]["difference"] == pytest.approx(-0.15)
    assert checks["similarity"]["drift"] is True
    assert checks["similarity_distribution"]["drift"] is True
    assert checks["refusals"]["drift"] is False  # every question still answered


def test_more_refusals_on_the_same_questions_show_as_drift() -> None:
    nights = [night(f"2026-11-1{n}", refused=1) for n in range(3)]
    nights += [night(f"2026-11-2{n}", refused=14) for n in range(3)]

    refusals = nightly_drift(nights)["checks"]["refusals"]

    assert (refusals["reference"], refusals["recent"]) == (0.05, 0.7)
    assert refusals["drift"] is True


def test_the_canary_compares_each_questions_first_time_with_its_latest() -> None:
    days = [day(f"2026-11-1{n}", seconds=10.0) for n in range(3)]
    days += [day(f"2026-11-2{n}", seconds=10.0 + 5 * n) for n in range(3)]
    days[-1]["rows"][0]["ok"] = False  # a failed request counts for nothing

    report = canary_drift(days)

    seconds = report["checks"]["seconds"]
    assert seconds["questions"] == 10
    assert seconds["reference"] == pytest.approx(10.45)  # each question's first time
    assert seconds["recent"] > 19.0  # mostly the last day's, 10 seconds slower
    assert seconds["drift"] is True
    assert report["checks"]["similarity"]["drift"] is False


def test_per_question_means_skip_what_wasnt_recorded() -> None:
    periods = [night("a", similarity=0.5), night("b"), night("c", similarity=0.7)]

    means = per_question(periods, "copilot", "similarity")

    assert means["q00"] == pytest.approx(0.6)
    assert len(means) == 20
