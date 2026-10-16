"""Flatten SEC company-facts JSON into fact, concept and filing rows (ADR-0008).

Only facts from annual and quarterly reports (10-K, 10-Q, their amendments and transition
reports) are kept.

A filing's period end comes from its `us-gaap` facts that cover a whole fiscal year (in a
10-K), a quarter (in a 10-Q) or the transition period (in a 10-KT, such as Best Buy's
11-month year to February 2013) and end on or before the filing date. The income statement and
cash flow statement report the current period, so it is the most common end date within
two weeks of the latest one. Each rule handles a case seen in real filings:

- comparatives end a year earlier, so they fall outside the two-week window;
- the filing-date limit drops forward-looking facts, such as next year's pension
  contributions (Boeing's FY2017 10-K has one ending in December 2018);
- taking the most common date absorbs stray contexts a day off (Foot Locker's FY2013
  10-K has a few facts ending 2014-02-02 against its year end of 2014-02-01);
- counting end dates across all facts fails, because equity statements add balances at
  earlier dates (it put Nike's FY2010 balance sheet at 2009-05-31).

A 10-K's fiscal year label is derived from its period end, not taken from SEC's `fy`,
which is sometimes wrong (Best Buy's FY2021 10-K says 2020, duplicating FY2020).
Companies name fiscal years in one of two ways: by the year they end in (Walmart's year
ending January 2023 is FY2023) or by the year most of their days fall in (Ulta's year
ending January 2023 is FY2022). For each company, the way that agrees with more of SEC's
labels wins, so one wrong label can't flip it. Quarterly filings keep SEC's labels.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

REPORT_FORMS = frozenset({"10-K", "10-K/A", "10-KT", "10-KT/A", "10-Q", "10-Q/A"})
ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "10-KT", "10-KT/A"})
ANNUAL_DAYS = range(350, 381)  # a fiscal year, including 52/53-week years (364 or 371 days)
QUARTER_DAYS = range(80, 101)  # a fiscal quarter of 12 to 14 weeks
TRANSITION_DAYS = range(28, 381)  # a transition report (10-KT) can cover any part of a year
TRANSITION_FORMS = frozenset({"10-KT", "10-KT/A"})


@dataclass(frozen=True, slots=True)
class Fact:
    cik: int
    taxonomy: str
    tag: str
    unit: str
    start: str | None
    end: str
    value: float
    accn: str
    form: str
    filed: str
    fy: int | None
    fp: str | None
    frame: str | None


@dataclass(frozen=True, slots=True)
class Concept:
    taxonomy: str
    tag: str
    label: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Filing:
    accn: str
    cik: int
    form: str
    filed: str
    fy: int | None
    fp: str | None
    period_end: str
    fiscal_year: int | None


def iter_facts(
    company_facts: Mapping[str, Any], forms: frozenset[str] = REPORT_FORMS
) -> Iterator[Fact]:
    """Every fact from the given forms, once per filing (exact repeats are dropped)."""
    cik = int(company_facts["cik"])
    seen: set[tuple[str, str, str, str | None, str, str]] = set()
    for taxonomy, concepts in company_facts.get("facts", {}).items():
        for tag, body in concepts.items():
            for unit, entries in body.get("units", {}).items():
                for entry in entries:
                    if entry.get("form") not in forms:
                        continue
                    key = (taxonomy, tag, unit, entry.get("start"), entry["end"], entry["accn"])
                    if key in seen:
                        continue
                    seen.add(key)
                    yield Fact(
                        cik=cik,
                        taxonomy=taxonomy,
                        tag=tag,
                        unit=unit,
                        start=entry.get("start"),
                        end=entry["end"],
                        value=float(entry["val"]),
                        accn=entry["accn"],
                        form=entry["form"],
                        filed=entry["filed"],
                        fy=entry.get("fy"),
                        fp=entry.get("fp"),
                        frame=entry.get("frame"),
                    )


def iter_concepts(company_facts: Mapping[str, Any]) -> Iterator[Concept]:
    for taxonomy, concepts in company_facts.get("facts", {}).items():
        for tag, body in concepts.items():
            yield Concept(taxonomy, tag, body.get("label"), body.get("description"))


def _full_period_days(form: str) -> range:
    if form in TRANSITION_FORMS:
        return TRANSITION_DAYS
    return ANNUAL_DAYS if form in ANNUAL_FORMS else QUARTER_DAYS


def duration_days(start: str | None, end: str) -> int | None:
    if start is None:
        return None
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def filings_from(facts: Iterable[Fact]) -> dict[str, Filing]:
    """One row per filing, with its period end found as the module describes."""
    first: dict[str, Fact] = {}
    full_period_ends: dict[str, Counter[str]] = {}
    all_ends: dict[str, Counter[str]] = {}
    for fact in facts:
        filing = first.setdefault(fact.accn, fact)
        if fact.taxonomy != "us-gaap":
            continue
        all_ends.setdefault(fact.accn, Counter())[fact.end] += 1
        days = _full_period_days(filing.form)
        if fact.end <= filing.filed and duration_days(fact.start, fact.end) in days:
            full_period_ends.setdefault(fact.accn, Counter())[fact.end] += 1
    filings = {}
    for accn, fact in first.items():
        counts = full_period_ends.get(accn)
        if counts:
            latest = date.fromisoformat(max(counts))
            counts = Counter(
                {
                    end: n
                    for end, n in counts.items()
                    if (latest - date.fromisoformat(end)).days <= 14
                }
            )
        else:  # no full-period facts: fall back to every end date the filing uses
            counts = all_ends.get(accn) or Counter({fact.end: 1})
        period_end = max(counts, key=lambda end: (counts[end], end))
        filings[accn] = Filing(
            accn, fact.cik, fact.form, fact.filed, fact.fy, fact.fp, period_end, fact.fy
        )
    labels = fiscal_year_labels(filings.values())
    return {accn: replace(f, fiscal_year=labels.get(accn, f.fy)) for accn, f in filings.items()}


def _end_year(period_end: str) -> int:
    return int(period_end[:4])


def _mid_year(period_end: str) -> int:
    return (date.fromisoformat(period_end) - timedelta(days=182)).year


def fiscal_year_labels(filings: Iterable[Filing]) -> dict[str, int]:
    """Each annual filing's fiscal year, named the way its company names them."""
    by_company: dict[int, list[Filing]] = {}
    for filing in filings:
        if filing.form in ANNUAL_FORMS:
            by_company.setdefault(filing.cik, []).append(filing)
    labels: dict[str, int] = {}
    for annual in by_company.values():
        end_votes = sum(f.fy == _end_year(f.period_end) for f in annual)
        mid_votes = sum(f.fy == _mid_year(f.period_end) for f in annual)
        name = _end_year if end_votes >= mid_votes else _mid_year
        labels |= {f.accn: name(f.period_end) for f in annual}
    return labels
