"""Matching FinanceBench company names to SEC filers."""

from __future__ import annotations

from pathlib import Path

import pytest

from copilot.ingest.sec import Ticker
from copilot.ingest.universe import (
    COMPANIES_FILE,
    Company,
    match_companies,
    normalise_name,
    read_companies,
    write_companies,
)

ROOT = Path(__file__).resolve().parents[1]

TICKERS = [
    Ticker(cik_str=66740, ticker="MMM", title="3M CO"),
    Ticker(cik_str=909832, ticker="COST", title="COSTCO WHOLESALE CORP /NEW"),
    Ticker(cik_str=21344, ticker="KO", title="COCA COLA CO"),
    Ticker(cik_str=63908, ticker="MCD", title="MCDONALDS CORP"),
    Ticker(cik_str=1633917, ticker="PYPL", title="PayPal Holdings, Inc."),
    Ticker(cik_str=19617, ticker="JPM", title="JPMORGAN CHASE & CO"),
]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("COSTCO WHOLESALE CORP /NEW", "costco wholesale"),
        ("CORNING INC /NY", "corning"),
        ("McDonald's", "mcdonalds"),
        ("PG&E Corp", "pg and e"),
        ("Coca-Cola", "coca cola"),
        ("PayPal Holdings, Inc.", "paypal"),
        ("The Coca-Cola Company", "coca cola"),
    ],
)
def test_normalise_name(name: str, expected: str) -> None:
    assert normalise_name(name) == expected


def test_names_match_after_normalising() -> None:
    matches = {
        m.name: m for m in match_companies(["3M", "Coca-Cola", "McDonalds", "Paypal"], TICKERS)
    }

    assert {name: m.cik for name, m in matches.items()} == {
        "3M": 66740,
        "Coca-Cola": 21344,
        "McDonalds": 63908,
        "Paypal": 1633917,
    }
    assert {m.matched_by for m in matches.values()} == {"name"}


def test_overrides_cover_names_and_delisted_companies() -> None:
    matches = {
        m.name: m for m in match_companies(["JPMorgan", "Costco", "Activision Blizzard"], TICKERS)
    }

    assert (matches["JPMorgan"].cik, matches["JPMorgan"].matched_by) == (19617, "ticker override")
    assert matches["Costco"].ticker == "COST"
    assert matches["Activision Blizzard"].cik == 718877
    assert matches["Activision Blizzard"].ticker is None
    assert matches["Activision Blizzard"].matched_by == "CIK override"


def test_an_unmatched_name_is_an_error() -> None:
    with pytest.raises(LookupError, match="Nonexistent Widgets"):
        match_companies(["3M", "Nonexistent Widgets"], TICKERS)


def test_companies_round_trip_through_csv(tmp_path: Path) -> None:
    companies = [
        Company(
            name="Activision Blizzard",
            cik=718877,
            ticker=None,
            sec_name="Activision Blizzard, Inc.",
            sector="Communication Services",
            fiscal_year_end="1231",
            matched_by="CIK override",
        )
    ]
    path = tmp_path / "companies.csv"

    write_companies(companies, path)

    assert read_companies(path) == companies


def test_committed_universe_covers_every_financebench_company() -> None:
    companies = read_companies(ROOT / COMPANIES_FILE)

    assert len(companies) == 40
    assert len({c.cik for c in companies}) == 40
    assert {c.name for c in companies if c.ticker is None} == {"Activision Blizzard", "Foot Locker"}
    assert all(len(c.fiscal_year_end) == 4 for c in companies)
