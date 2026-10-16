"""Normalising company facts, annual values, the database and the FinanceBench cross-checks.

The synthetic company below reproduces the cases seen in real filings: comparatives in later
10-Ks, a restatement, a tag change, equity-statement balances at earlier dates, a
forward-looking fact, a stray context a day off, a 10-Q and an 8-K.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from copilot.eval.splits import SPLIT_FILE, read_split_file
from copilot.facts import checks, database
from copilot.facts.formula import lookups
from copilot.facts.metrics import METRICS_BY_NAME, annual_values, is_annual_period
from copilot.facts.normalise import (
    Fact,
    Filing,
    filings_from,
    fiscal_year_labels,
    iter_concepts,
    iter_facts,
)
from copilot.ingest.universe import Company

ROOT = Path(__file__).resolve().parents[1]
CIK = 1234
K21: dict[str, Any] = {
    "accn": "0000001234-22-000001",
    "form": "10-K",
    "filed": "2022-02-10",
    "fy": 2021,
    "fp": "FY",
}
K22: dict[str, Any] = {
    "accn": "0000001234-23-000001",
    "form": "10-K",
    "filed": "2023-02-10",
    "fy": 2022,
    "fp": "FY",
}
Q22: dict[str, Any] = {
    "accn": "0000001234-22-000002",
    "form": "10-Q",
    "filed": "2022-05-05",
    "fy": 2022,
    "fp": "Q1",
}
EIGHT_K: dict[str, Any] = {
    "accn": "0000001234-22-000003",
    "form": "8-K",
    "filed": "2022-02-01",
    "fy": 2021,
    "fp": "FY",
}


def _entry(
    filing: dict[str, Any], end: str, val: float, start: str | None = None
) -> dict[str, Any]:
    entry = {"end": end, "val": val, **filing}
    if start is not None:
        entry["start"] = start
    return entry


def _concept(label: str, unit: str, *entries: dict[str, Any]) -> dict[str, Any]:
    return {"label": label, "description": f"{label}.", "units": {unit: list(entries)}}


def company_facts() -> dict[str, Any]:
    year21 = ("2021-01-01", "2021-12-31")
    year20 = ("2020-01-01", "2020-12-31")
    return {
        "cik": CIK,
        "entityName": "ACME CORP",
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": _concept(
                    "Shares outstanding", "shares", _entry(K21, "2022-02-01", 1e6)
                )
            },
            "us-gaap": {
                "Revenues": _concept(
                    "Revenues",
                    "USD",
                    _entry(K21, year21[1], 100.0, year21[0]),
                    _entry(K21, year20[1], 90.0, year20[0]),
                    _entry(K22, year21[1], 101.0, year21[0]),  # restated comparative
                    _entry(Q22, "2022-03-31", 28.0, "2022-01-01"),
                    _entry(EIGHT_K, year21[1], 99.0, year21[0]),
                ),
                "RevenueFromContractWithCustomerExcludingAssessedTax": _concept(
                    "Revenue from contracts",
                    "USD",
                    _entry(K22, "2022-12-31", 120.0, "2022-01-01"),  # tag change in FY2022
                ),
                "OperatingIncomeLoss": _concept(
                    "Operating income",
                    "USD",
                    _entry(K21, year21[1], 20.0, year21[0]),
                    _entry(K21, "2022-01-01", 1.0, "2021-01-02"),  # a stray context a day off
                ),
                "Assets": _concept(
                    "Assets",
                    "USD",
                    _entry(K21, "2021-12-31", 500.0),
                    _entry(K21, "2020-12-31", 450.0),
                    _entry(K22, "2022-12-31", 550.0),
                    _entry(K22, "2021-12-31", 500.0),
                    _entry(Q22, "2022-03-31", 510.0),
                ),
                "StockholdersEquity": _concept(
                    "Equity",
                    "USD",
                    *(
                        _entry(K21, end, 300.0)
                        for end in ("2018-12-31", "2019-12-31", "2020-12-31")
                    ),
                    _entry(K21, "2021-12-31", 310.0),
                ),
                "DefinedBenefitPlanExpectedFutureEmployerContributionsNextFiscalYear": _concept(
                    "Expected contributions",
                    "USD",
                    _entry(K21, "2022-12-31", 5.0, "2022-01-01"),  # ends after the filing date
                ),
            },
        },
    }


@pytest.fixture
def facts_db(tmp_path: Path) -> Path:
    facts_dir = tmp_path / "companyfacts"
    facts_dir.mkdir()
    (facts_dir / f"CIK{CIK:010d}.json").write_text(json.dumps(company_facts()), encoding="utf-8")
    company = Company(
        name="Acme",
        cik=CIK,
        ticker="ACME",
        sec_name="ACME CORP",
        sector="Industrials",
        fiscal_year_end="1231",
        matched_by="name",
    )
    path = tmp_path / "facts.db"
    database.build(path, [company], facts_dir)
    return path


def test_only_report_forms_are_kept() -> None:
    facts = list(iter_facts(company_facts()))

    assert {f.form for f in facts} == {"10-K", "10-Q"}
    assert all(f.accn != EIGHT_K["accn"] for f in facts)


def test_concepts_carry_labels() -> None:
    concepts = {c.tag: c for c in iter_concepts(company_facts())}

    assert concepts["Revenues"].label == "Revenues"
    assert concepts["EntityCommonStockSharesOutstanding"].taxonomy == "dei"


def test_period_end_is_the_current_period_despite_distractors() -> None:
    filings = filings_from(iter_facts(company_facts()))

    assert filings[K21["accn"]].period_end == "2021-12-31"
    assert filings[K22["accn"]].period_end == "2022-12-31"
    assert filings[Q22["accn"]].period_end == "2022-03-31"


def _filing(accn: str, period_end: str, fy: int, cik: int, form: str = "10-K") -> Filing:
    return Filing(accn, cik, form, "2030-01-01", fy, "FY", period_end, fy)


def test_fiscal_year_labels_follow_each_company_convention() -> None:
    # Walmart names a year by the January it ends in; Ulta by the year most of it falls in.
    walmart = [_filing(f"w{y}", f"{y}-01-31", y, cik=1) for y in (2019, 2020, 2021, 2022)]
    walmart[2] = replace(walmart[2], fy=2020)  # one wrong SEC label, as in Best Buy's FY2021
    ulta = [_filing(f"u{y}", f"{y + 1}-01-28", y, cik=2) for y in (2019, 2020, 2021)]
    quarter = _filing("q", "2022-04-30", 2023, cik=1, form="10-Q")

    labels = fiscal_year_labels([*walmart, *ulta, quarter])

    assert [labels[f.accn] for f in walmart] == [2019, 2020, 2021, 2022]
    assert [labels[f.accn] for f in ulta] == [2019, 2020, 2021]
    assert "q" not in labels  # quarterly filings keep SEC's label


def test_a_transition_report_ends_with_its_short_period() -> None:
    def fact(start: str, end: str) -> Fact:
        return Fact(
            1,
            "us-gaap",
            "Revenues",
            "USD",
            start,
            end,
            1.0,
            "t",
            "10-KT",
            "2013-03-27",
            2012,
            "FY",
            None,
        )

    filings = filings_from([fact("2012-03-04", "2013-02-02"), fact("2011-02-27", "2012-03-03")])

    assert filings["t"].period_end == "2013-02-02"  # an 11-month year, as at Best Buy


@pytest.mark.parametrize(
    ("start", "end", "annual"),
    [
        ("2021-01-01", "2021-12-31", True),
        ("2021-01-03", "2022-01-01", True),  # a 52-week year
        ("2020-12-27", "2022-01-01", True),  # a 53-week year
        ("2021-07-01", "2021-12-31", False),
        (None, "2021-12-31", False),
    ],
)
def test_is_annual_period(start: str | None, end: str, annual: bool) -> None:
    assert is_annual_period(start, end) is annual


def test_annual_revenue_uses_original_reports_and_follows_tag_changes() -> None:
    facts = list(iter_facts(company_facts()))
    values = {
        v.fiscal_year: v
        for v in annual_values(facts, filings_from(facts), METRICS_BY_NAME["revenue"])
    }

    assert set(values) == {2021, 2022}
    assert (values[2021].value, values[2021].tag) == (100.0, "Revenues")
    assert (values[2021].latest_value, values[2021].latest_accn) == (101.0, K22["accn"])
    assert (values[2022].value, values[2022].tag) == (
        120.0,
        "RevenueFromContractWithCustomerExcludingAssessedTax",
    )


def test_annual_instant_values_come_from_each_year_end() -> None:
    facts = list(iter_facts(company_facts()))
    values = annual_values(facts, filings_from(facts), METRICS_BY_NAME["total_assets"])

    assert [(v.fiscal_year, v.end, v.value) for v in values] == [
        (2021, "2021-12-31", 500.0),
        (2022, "2022-12-31", 550.0),
    ]


def test_database_tables_and_read_only_access(facts_db: Path) -> None:
    conn = database.connect_read_only(facts_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0] == 3
        revenue = conn.execute(
            "SELECT fiscal_year, value FROM annual_values WHERE metric = 'revenue' ORDER BY 1"
        ).fetchall()
        assert revenue == [(2021, 100.0), (2022, 120.0)]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM facts")
    finally:
        conn.close()


def test_connect_read_only_needs_a_built_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="build-facts"):
        database.connect_read_only(tmp_path / "missing.db")


@pytest.mark.parametrize(
    ("answer", "value"),
    [("$1577.00", 1577.0), ("1.9%", 1.9), ("-3.7", -3.7), ("$12,645.00", 12645.0)],
)
def test_parse_answer(answer: str, value: float) -> None:
    assert checks.parse_answer(answer) == value


def test_agreement_is_exact_at_the_question_precision() -> None:
    assert checks.agrees(1615.9, 1616.0, 0)
    assert checks.agrees(0.389, 0.4, 1)
    assert not checks.agrees(0.389, 0.4, 2)


def test_run_checks(facts_db: Path) -> None:
    conn = database.connect_read_only(facts_db)
    specs = [
        checks.Check(
            id="q1", company="Acme", formula="(revenue[2022] / revenue[2021] - 1) * 100", decimals=1
        ),
        checks.Check(id="q2", company="Acme", formula="revenue[2019]", decimals=0),
    ]
    try:
        first, second = checks.run_checks(conn, specs, {"q1": "20.0%", "q2": "$1"}, {"Acme": CIK})
        with pytest.raises(KeyError, match="dev"):
            checks.run_checks(conn, specs, {"q1": "20.0%"}, {"Acme": CIK})
    finally:
        conn.close()

    assert first.computed == pytest.approx(20.0)
    assert first.agrees
    assert "revenue: Revenues" in first.detail
    assert (second.computed, second.agrees, second.detail) == (None, False, "no revenue for FY2019")


def test_committed_checks_use_dev_questions_and_known_metrics() -> None:
    specs = checks.load_checks(ROOT / checks.CHECKS_FILE)
    dev = set(read_split_file(ROOT / SPLIT_FILE).dev)

    assert len(specs) == 33
    assert {spec.id for spec in specs} <= dev
    for spec in specs:
        assert {metric for metric, _ in lookups(spec.formula)} <= set(METRICS_BY_NAME)


def test_the_dictionary_lists_every_metric() -> None:
    text = (ROOT / "docs" / "data" / "facts-dictionary.md").read_text(encoding="utf-8")

    assert [name for name in METRICS_BY_NAME if f"`{name}`" not in text] == []


def test_descriptions_cover_every_table() -> None:
    descriptions = json.loads(
        (ROOT / "data/reference/facts_descriptions.json").read_text(encoding="utf-8")
    )

    assert sorted(descriptions) == sorted(re.findall(r"CREATE TABLE (\w+)", database.SCHEMA))
