"""Query understanding: companies, periods, forms and the filings they resolve to."""

from __future__ import annotations

import pytest

from copilot.eval.financebench import Document
from copilot.retrieval.query import (
    CompanyMatcher,
    Filing,
    QueryCues,
    filings_from,
    resolve,
    understand,
)

MATCHER = CompanyMatcher(
    [
        "3M",
        "Johnson & Johnson",
        "JPMorgan",
        "American Water Works",
        "Block",
        "Costco",
        "MGM Resorts",
        "AES Corporation",
        "PG&E Corporation",
        "Coca-Cola",
    ],
    {
        "3M": "MMM",
        "Johnson & Johnson": "JNJ",
        "JPMorgan": "JPM",
        "American Water Works": "AWK",
        "Block": "XYZ",
        "Costco": "COST",
        "MGM Resorts": "MGM",
        "AES Corporation": "AES",
        "PG&E Corporation": "PCG",
        "Coca-Cola": "KO",
    },
)


@pytest.mark.parametrize(
    ("question", "companies"),
    [
        ("What is the FY2018 capital expenditure for 3M?", ("3M",)),
        ("Did JnJ's net earnings rise in Q2 of FY2023?", ("Johnson & Johnson",)),
        ("How much could each JPM shareholder get?", ("JPMorgan",)),
        ("Does American Water Works have positive working capital?", ("American Water Works",)),
        ("What drove Block's revenue in 2021?", ("Block",)),
        ("Was the block of shares sold at a discount?", ()),
        ("Did Costco's membership fees grow, and what was the cost of sales?", ("Costco",)),
        ("Which region had the highest EBITDAR for MGM during FY2022?", ("MGM Resorts",)),
        ("What was the AES Corporation's FY2022 net income?", ("AES Corporation",)),
        ("How large were PG&E's wildfire liabilities?", ("PG&E Corporation",)),
        ("Did coca cola raise its dividend?", ("Coca-Cola",)),
        ("Were there any board member nominees with many votes against?", ()),
    ],
)
def test_companies_are_found_by_name_alias_and_ticker(
    question: str, companies: tuple[str, ...]
) -> None:
    assert understand(question, MATCHER).companies == companies


@pytest.mark.parametrize(
    ("question", "years", "quarters"),
    [
        ("What is the FY2018 capex?", (2018,), ()),
        ("What was revenue in FY22?", (2022,), ()),
        ("In fiscal 2021, what was the margin?", (2021,), ()),
        ("Did sales grow during 2022?", (2022,), ()),
        ("Compare Q2 of FY2023 with Q2 of FY2022.", (2022, 2023), ((2022, 2), (2023, 2))),
        ("If it went bankrupt by the end of 2021 Q1, what then?", (2021,), ((2021, 1),)),
        ("What happened in the second fiscal quarter of 2023?", (2023,), ((2023, 2),)),
        ("How did 2Q23 margins compare?", (2023,), ((2023, 2),)),
        ("What was the Q4 FY 2022 operating income?", (2022,), ((2022, 4),)),
    ],
)
def test_periods_are_read_in_their_usual_forms(
    question: str, years: tuple[int, ...], quarters: tuple[tuple[int, int], ...]
) -> None:
    cues = understand(question, MATCHER)

    assert (cues.years, cues.quarters) == (years, quarters)


def test_dates_forms_and_outlook_are_read() -> None:
    dated = understand(
        "What was the key agenda of the AMCOR 8k filing dated 1st July 2022?", MATCHER
    )
    as_of = understand("What cash did JnJ realise as of August 30, 2023?", MATCHER)
    outlook = understand("Is JnJ's EPS growth expected to accelerate in FY2023?", MATCHER)

    assert dated.dates == ((2022, 7, 1),)
    assert dated.forms == ("8k",)
    assert as_of.dates == ((2023, 8, 30),)
    assert understand("Per the 10-K, what was 3M's debt?", MATCHER).forms == ("10k",)
    assert outlook.outlook
    assert not understand("What was 3M's FY2018 capex?", MATCHER).outlook


def _filing(name: str, form: str, year: int, quarter: int | None = None) -> Filing:
    return Filing(name, "Acme", form, year, quarter)


FILINGS = [
    _filing("ACME_2022_10K", "10k", 2022),
    _filing("ACME_2023_10K", "10k", 2023),
    _filing("ACME_2023Q2_10Q", "10q", 2023, 2),
    _filing("ACME_2022Q4_EARNINGS", "earnings", 2022, 4),
    Filing("ACME_2023_8K_dated-2023-08-30", "Acme", "8k", 2023, None, (2023, 8, 30)),
    Filing("BOLT_2022_10K", "Bolt", "10k", 2022),
]


def test_resolve_keeps_the_company_and_period_and_prefers_the_form_asked_for() -> None:
    fy2022 = QueryCues(companies=("Acme",), years=(2022,))
    q2 = QueryCues(companies=("Acme",), years=(2023,), quarters=((2023, 2),))
    annual = QueryCues(companies=("Acme",), years=(2022,), forms=("10k",))
    dated = QueryCues(companies=("Acme",), years=(2023,), dates=((2023, 8, 30),))
    outlook = QueryCues(companies=("Acme",), years=(2023,), outlook=True)

    assert resolve(fy2022, FILINGS) == ["ACME_2022Q4_EARNINGS", "ACME_2022_10K"]
    assert resolve(q2, FILINGS) == ["ACME_2023Q2_10Q", "ACME_2023_10K"]
    assert resolve(annual, FILINGS) == ["ACME_2022_10K"]
    assert resolve(dated, FILINGS) == ["ACME_2023_10K", "ACME_2023_8K_dated-2023-08-30"]
    assert "ACME_2022Q4_EARNINGS" in (resolve(outlook, FILINGS) or [])


def test_resolve_falls_back_to_the_company_or_to_everything() -> None:
    no_match = QueryCues(companies=("Acme",), years=(2015,))

    assert resolve(no_match, FILINGS) == sorted(f.doc_name for f in FILINGS[:5])
    assert resolve(QueryCues(years=(2022,)), FILINGS) is None


def test_filings_read_quarters_and_dates_from_document_names() -> None:
    def document(name: str, doc_type: str, period: int) -> Document:
        return Document(
            doc_name=name,
            company="Acme",
            gics_sector="Industrials",
            doc_type=doc_type,
            doc_period=period,
            doc_link="https://example.com",
        )

    filings = filings_from(
        [
            document("ACME_2023Q2_10Q", "10q", 2023),
            document("ACME_2022_8K_dated_2022-08-19", "8k", 2022),
            document("ACME_2022_10K", "10k_annualreport", 2022),
        ]
    )

    assert filings[0].quarter == 2
    assert filings[1].date == (2022, 8, 19)
    assert filings[2].form == "10k"
