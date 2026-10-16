"""The company universe: FinanceBench's companies, matched to SEC CIKs and tickers.

Names are matched to SEC's ticker list after normalising both sides: case, punctuation,
"&", and suffixes such as Inc., Corp. or plc. Names that can't match that way are listed in
the override tables, by ticker where SEC still lists one and by CIK for companies that no
longer trade. Every match is then checked against the company's SEC submissions record,
and the result is committed as `data/reference/companies.csv`.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from copilot.ingest.sec import Ticker

COMPANIES_FILE = Path("data/reference/companies.csv")

# FinanceBench names that differ too much from SEC's titles to match after normalising
# ("JPMorgan" is "JPMORGAN CHASE & CO", "AMD" is "ADVANCED MICRO DEVICES INC").
TICKER_OVERRIDES: dict[str, str] = {
    "AMD": "AMD",
    "Amazon": "AMZN",
    "Costco": "COST",
    "JPMorgan": "JPM",
    "MGM Resorts": "MGM",
    "Verizon": "VZ",
}
# Companies that no longer trade, so SEC's ticker list leaves them out.
CIK_OVERRIDES: dict[str, int] = {
    "Activision Blizzard": 718877,  # acquired by Microsoft in October 2023
    "Foot Locker": 850209,  # no longer trades; SEC's ticker list leaves it out
}

MatchedBy = Literal["name", "ticker override", "CIK override"]

_SUFFIXES = frozenset(
    {"inc", "incorporated", "corp", "corporation", "co", "company", "plc", "ltd", "the", "holdings"}
)
_APOSTROPHES = str.maketrans("", "", "'" + chr(0x2019))
_STATE_SUFFIX = re.compile(r"\s*/[a-z]+\s*$")  # SEC titles such as "CORNING INC /NY"
_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


class Company(BaseModel):
    """One company in the universe, as written to `companies.csv`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    cik: int
    ticker: str | None
    sec_name: str
    sector: str
    fiscal_year_end: str
    matched_by: MatchedBy


@dataclass(frozen=True, slots=True)
class Match:
    name: str
    cik: int
    ticker: str | None
    matched_by: MatchedBy


def normalise_name(name: str) -> str:
    """Lower case, '&' as 'and', no punctuation, no state tags and no corporate suffixes."""
    text = _STATE_SUFFIX.sub("", name.lower().translate(_APOSTROPHES))
    words = _NOT_ALPHANUMERIC.sub(" ", text.replace("&", " and ")).split()
    return " ".join(word for word in words if word not in _SUFFIXES)


def match_companies(names: Iterable[str], tickers: Sequence[Ticker]) -> list[Match]:
    """Match each name to a CIK and ticker, raising if any name finds no match."""
    by_title: dict[str, Ticker] = {}
    for row in tickers:  # SEC ranks the list, so the first row for a title wins
        by_title.setdefault(normalise_name(row.title), row)
    by_ticker = {row.ticker: row for row in tickers}
    first_ticker_for_cik: dict[int, str] = {}
    for row in tickers:
        first_ticker_for_cik.setdefault(row.cik_str, row.ticker)

    matches: list[Match] = []
    missing: list[str] = []
    for name in sorted(set(names)):
        if name in CIK_OVERRIDES:
            cik = CIK_OVERRIDES[name]
            matches.append(Match(name, cik, first_ticker_for_cik.get(cik), "CIK override"))
        elif name in TICKER_OVERRIDES:
            row = by_ticker[TICKER_OVERRIDES[name]]
            matches.append(Match(name, row.cik_str, row.ticker, "ticker override"))
        elif (found := by_title.get(normalise_name(name))) is not None:
            matches.append(Match(name, found.cik_str, found.ticker, "name"))
        else:
            missing.append(name)
    if missing:
        raise LookupError(
            f"No SEC match for {', '.join(missing)}; add them to TICKER_OVERRIDES or CIK_OVERRIDES."
        )
    return matches


def write_companies(companies: Sequence[Company], path: Path = COMPANIES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(Company.model_fields), lineterminator="\n")
        writer.writeheader()
        for company in companies:
            writer.writerow(company.model_dump())


def read_companies(path: Path = COMPANIES_FILE) -> list[Company]:
    with path.open(encoding="utf-8", newline="") as rows:
        return [
            Company.model_validate({**row, "ticker": row["ticker"] or None})
            for row in csv.DictReader(rows)
        ]
