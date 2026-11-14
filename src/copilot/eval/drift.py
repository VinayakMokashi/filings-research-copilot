"""Drift checks (step 9.5): is the running system behaving differently on the same inputs?

Three signals, each read where it is clean:

- **Retrieval similarity**, from the nightly evaluation: the cosine similarity between each
  question and the best chunk its own search finds. The nightly run asks the same
  questions every night, so a question's similarity moves only when the collection, the
  embedding model or the vector store changes. It is compared question by question (a
  paired permutation test) and as a distribution (the two-sample Kolmogorov-Smirnov
  statistic, its p-value from relabelling). The canary records it too, on the live API.
- **Refusals**, from the nightly evaluation: each question's share of nights it went
  unanswered, compared question by question.
- **Latency**, from the daily canary: the live API's own time for a question. The nightly
  run's seconds are paced for the free tier, so they measure throughput, not a reader's
  wait. Each canary question's latest time is compared with its first.

For each signal the first `window` nights (or days) that recorded it are the reference,
and the last `window` the recent period; with fewer than twice as many, it isn't compared
yet. A check's tests are Holm-adjusted together, and a drift is a difference whose adjusted
p-value is below 0.05. Drifts are reported in the night's or the day's history line, not
alarmed: three nights are few, and a provider's change shows in the regression tests
first.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean
from typing import Any

import numpy as np

from copilot.eval.stats import RESAMPLES, holm, paired_test

WINDOW = 3
ALPHA = 0.05
# Slack when comparing relabelled gaps with the observed one, so exact ties count as ties.
TIE = 1e-12


def ks_test(
    a: Sequence[float], b: Sequence[float], *, resamples: int = RESAMPLES, seed: int = 0
) -> tuple[float, float]:
    """The two-sample Kolmogorov-Smirnov statistic, the largest gap between the two samples'
    empirical distribution functions, and its p-value: the share of random relabellings of
    the pooled values with a gap at least as large, the observed one counted once."""
    first, second = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if first.size == 0 or second.size == 0:
        raise ValueError("Both samples need values.")

    def gap(x: np.ndarray, y: np.ndarray) -> float:
        points = np.concatenate([x, y])
        cdf_x = np.searchsorted(np.sort(x), points, side="right") / x.size
        cdf_y = np.searchsorted(np.sort(y), points, side="right") / y.size
        return float(np.max(np.abs(cdf_x - cdf_y)))

    observed = gap(first, second)
    pooled = np.concatenate([first, second])
    rng = np.random.default_rng(seed)
    as_large = 0
    for _ in range(resamples):
        shuffled = rng.permutation(pooled)
        if gap(shuffled[: first.size], shuffled[first.size :]) >= observed - TIE:
            as_large += 1
    return observed, (as_large + 1) / (resamples + 1)


def per_question(periods: Sequence[Mapping[str, Any]], part: str, key: str) -> dict[str, float]:
    """Each question's mean of `key` over the periods' rows in `part`, where it is recorded."""
    values: dict[str, list[float]] = {}
    for period in periods:
        for row in period.get(part) or []:
            if row.get(key) is not None:
                values.setdefault(str(row["id"]), []).append(float(row[key]))
    return {question: fmean(found) for question, found in values.items()}


def _recorded(periods: Sequence[Mapping[str, Any]], part: str, key: str) -> list[Mapping[str, Any]]:
    """The periods, in date order, with `key` recorded for at least one question."""
    found = [p for p in periods if any(r.get(key) is not None for r in p.get(part) or [])]
    return sorted(found, key=lambda period: str(period.get("date", "")))


def _paired(reference: Mapping[str, float], recent: Mapping[str, float]) -> dict[str, Any] | None:
    shared = sorted(set(reference) & set(recent))
    if len(shared) < 2:
        return None
    test = paired_test([reference[q] for q in shared], [recent[q] for q in shared])
    return {
        "questions": len(shared),
        "reference": round(test.mean_a, 4),
        "recent": round(test.mean_b, 4),
        "difference": round(test.difference.mean, 4),
        "low": round(test.difference.low, 4),
        "high": round(test.difference.high, 4),
        "p": test.p_value,
    }


def _windows(
    periods: Sequence[Mapping[str, Any]], part: str, key: str, window: int
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]] | None:
    usable = _recorded(periods, part, key)
    if len(usable) < 2 * window:
        return None
    return usable[:window], usable[-window:]


def _adjusted(checks: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """The checks with their Holm-adjusted p-values and drift flags."""
    found = {name: check for name, check in checks.items() if check is not None}
    for check, adjusted in zip(found.values(), holm([c["p"] for c in found.values()]), strict=True):
        check["p_holm"] = adjusted
        check["drift"] = adjusted < ALPHA
    return {name: checks[name] for name in checks}


def nightly_drift(nights: Sequence[Mapping[str, Any]], window: int = WINDOW) -> dict[str, Any]:
    """Retrieval similarity and refusals: the first nights that recorded each against the
    last."""
    checks: dict[str, dict[str, Any] | None] = {}
    spans: dict[str, Any] = {}
    similarity = _windows(nights, "copilot", "similarity", window)
    if similarity is not None:
        reference, recent = similarity
        before = per_question(reference, "copilot", "similarity")
        after = per_question(recent, "copilot", "similarity")
        checks["similarity"] = _paired(before, after)
        shared = sorted(set(before) & set(after))
        if len(shared) >= 2:
            statistic, p = ks_test([before[q] for q in shared], [after[q] for q in shared])
            checks["similarity_distribution"] = {"ks": round(statistic, 4), "p": p}
        spans["similarity"] = _dates(reference, recent)
    refusals = _windows(nights, "copilot", "answered", window)
    if refusals is not None:
        reference, recent = refusals
        before = {q: 1.0 - v for q, v in per_question(reference, "copilot", "answered").items()}
        after = {q: 1.0 - v for q, v in per_question(recent, "copilot", "answered").items()}
        checks["refusals"] = _paired(before, after)
        spans["refusals"] = _dates(reference, recent)
    return {"window": window, "periods": spans, "checks": _adjusted(checks)}


def canary_drift(days: Sequence[Mapping[str, Any]], window: int = WINDOW) -> dict[str, Any]:
    """Latency and retrieval similarity on the live API: each canary question's first value
    in the reference days against its latest in the recent ones."""
    checks: dict[str, dict[str, Any] | None] = {}
    spans: dict[str, Any] = {}
    for key in ("seconds", "similarity"):
        found = _windows(days, "rows", key, window)
        if found is None:
            continue
        reference, recent = found
        checks[key] = _paired(_first(reference, key), _latest(recent, key))
        spans[key] = _dates(reference, recent)
    return {"window": window, "periods": spans, "checks": _adjusted(checks)}


def _answered_rows(day: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in day.get("rows") or [] if row.get("ok")]


def _first(days: Sequence[Mapping[str, Any]], key: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for day in days:
        for row in _answered_rows(day):
            if row.get(key) is not None:
                found.setdefault(str(row["id"]), float(row[key]))
    return found


def _latest(days: Sequence[Mapping[str, Any]], key: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for day in days:
        for row in _answered_rows(day):
            if row.get(key) is not None:
                found[str(row["id"])] = float(row[key])
    return found


def _dates(
    reference: Sequence[Mapping[str, Any]], recent: Sequence[Mapping[str, Any]]
) -> dict[str, list[str]]:
    return {
        "reference": [str(period.get("date")) for period in reference],
        "recent": [str(period.get("date")) for period in recent],
    }
