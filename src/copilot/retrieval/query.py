"""Query understanding: which company, period and form a question is about (step 3.1).

Analyst questions usually name the company and the period: "What is the FY2018 capital
expenditure for 3M?", "Did JnJ's net earnings rise in Q2 of FY2023?". Searching only the
filings that match keeps out other companies' and other years' near-identical passages,
which is where most corpus-wide misses came from in Phase 2. The rules are deterministic
and cost no model call:

- **company**: the universe's names, short names, tickers and a few common aliases
  ("JnJ", "Amex"), matched as whole words; tickers and names that are also ordinary words
  ("Block") must match their capitalisation;
- **period**: fiscal years (FY2022, FY22, fiscal 2022, a bare 2022), quarters (Q2 2023,
  Q2 of FY2023, 2021 Q1, 2Q23, "second fiscal quarter of 2023") and dates ("August 30,
  2023", "1st July 2022");
- **form**: 10-K or annual report, 10-Q or quarterly report, 8-K, and earnings release;
- **outlook**: words like "expected", "guidance" or "outlook". Companies state next year's
  outlook in the previous year's filings, so a forward-looking question about FY2023 also
  searches FY2022's.

`resolve` turns the cues into the filings to search: the company's filings whose fiscal
year, quarter or date matches, narrowed to the form asked for when there is one. With no
company it returns None, meaning search everything; when nothing matches the period it
falls back to all of the company's filings.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from copilot.eval.financebench import Document

FORMS = {"10k": "10k", "10k_annualreport": "10k", "10q": "10q", "8k": "8k", "Earnings": "earnings"}
QUARTERLY = frozenset({"10q", "earnings"})

# Names people use that the universe file doesn't list.
ALIASES: dict[str, tuple[str, ...]] = {
    "Johnson & Johnson": ("JnJ", "J&J", "Johnson and Johnson"),
    "JPMorgan": ("JP Morgan", "J.P. Morgan", "JPMorgan Chase"),
    "MGM Resorts": ("MGM",),
    "PepsiCo": ("Pepsi",),
    "Activision Blizzard": ("Activision",),
    "Kraft Heinz": ("Kraft",),
    "Ulta Beauty": ("Ulta",),
    "American Express": ("Amex",),
    "CVS Health": ("CVS",),
    "Block": ("Square",),
    "McDonalds": ("McDonald's", "McDonald"),
    "Walmart": ("Wal-Mart",),
    "Coca-Cola": ("Coca Cola", "Coke"),
    "PG&E Corporation": ("PG&E", "Pacific Gas and Electric"),
    "AES Corporation": ("AES",),
    "American Water Works": ("American Water",),
    "Lockheed Martin": ("Lockheed",),
    "Foot Locker": ("Footlocker",),
}
# Names that are also ordinary words: matched only with their capitalisation.
CASE_SENSITIVE = frozenset({"Block", "Square", "Coke"})

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))
_YEAR = r"(?:19[89]\d|20[0-4]\d)"
_FY = r"(?:fy|fiscal\s+year|fiscal)"

_QUARTER_PATTERNS = (
    re.compile(rf"\bq([1-4])\s*(?:of\s+)?(?:{_FY}\s*)?'?(\d{{4}}|\d{{2}})\b", re.I),
    re.compile(rf"\b({_YEAR})\s*q([1-4])\b", re.I),
    re.compile(r"\b([1-4])q\s*'?(\d{4}|\d{2})\b", re.I),
    re.compile(
        rf"\b(first|second|third|fourth)\s+(?:fiscal\s+)?quarter\s+(?:of\s+)?(?:{_FY}\s*)?({_YEAR})\b",
        re.I,
    ),
)
_FISCAL_YEAR = re.compile(rf"\b{_FY}\s*'?(\d{{4}}|\d{{2}})\b", re.I)
_BARE_YEAR = re.compile(rf"\b({_YEAR})\b")
_DATES = (
    re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+({_YEAR})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH})\.?,?\s+({_YEAR})\b", re.I),
)
_FORM_PATTERNS = (
    ("10k", re.compile(r"\b10-?k\b|\bannual report\b", re.I)),
    ("10q", re.compile(r"\b10-?q\b|\bquarterly report\b", re.I)),
    ("8k", re.compile(r"\b8-?k\b", re.I)),
    (
        "earnings",
        re.compile(r"\bearnings (?:release|report|call|announcement)\b|\bpress release\b", re.I),
    ),
)
_OUTLOOK = re.compile(
    r"\b(?:expect(?:s|ed|ation|ations)?|guidance|outlook|forecast(?:s|ed)?|project(?:s|ed|ion|ions))\b",
    re.I,
)
_DOC_QUARTER = re.compile(r"_(\d{4})Q([1-4])_")
_DOC_DATE = re.compile(r"dated[-_](\d{4})-(\d{2})-(\d{2})")


@dataclass(frozen=True, slots=True)
class Filing:
    """What the resolver needs to know about one filing."""

    doc_name: str
    company: str
    form: str  # 10k, 10q, 8k or earnings
    year: int  # the fiscal period FinanceBench gives it
    quarter: int | None = None
    date: tuple[int, int, int] | None = None


def filings_from(documents: Mapping[str, Document] | Iterable[Document]) -> list[Filing]:
    docs = documents.values() if isinstance(documents, Mapping) else documents
    filings = []
    for doc in docs:
        quarter = _DOC_QUARTER.search(doc.doc_name + "_")
        date = _DOC_DATE.search(doc.doc_name)
        filings.append(
            Filing(
                doc_name=doc.doc_name,
                company=doc.company,
                form=FORMS.get(doc.doc_type, doc.doc_type.lower()),
                year=doc.doc_period,
                quarter=int(quarter.group(2)) if quarter else None,
                date=(int(date.group(1)), int(date.group(2)), int(date.group(3))) if date else None,
            )
        )
    return filings


@dataclass(frozen=True, slots=True)
class QueryCues:
    companies: tuple[str, ...] = ()
    years: tuple[int, ...] = ()
    quarters: tuple[tuple[int, int], ...] = ()  # (year, quarter)
    dates: tuple[tuple[int, int, int], ...] = ()  # (year, month, day)
    forms: tuple[str, ...] = ()
    outlook: bool = False


def _year(text: str) -> int:
    value = int(text)
    return 2000 + value if value < 100 else value


class CompanyMatcher:
    """Finds the universe's companies in free text."""

    def __init__(self, names: Iterable[str], tickers: Mapping[str, str | None]) -> None:
        patterns: list[tuple[str, re.Pattern[str]]] = []
        for name in names:
            variants = {name, *ALIASES.get(name, ())}
            short = re.sub(r"\s+(?:Corporation|Corp|Inc|Resorts|Beauty|Health)\.?$", "", name)
            if short and short != name and short not in {"PG&E"}:
                variants.add(short)
            for variant in variants:
                flags = 0 if variant in CASE_SENSITIVE else re.I
                body = re.escape(variant).replace(r"\ ", r"\s+")
                patterns.append((name, re.compile(rf"(?<![\w&]){body}(?:'s|s')?(?![\w&])", flags)))
            ticker = tickers.get(name)
            if ticker and len(ticker) >= 3:
                patterns.append((name, re.compile(rf"(?<![\w$]){re.escape(ticker)}(?![\w])")))
        # Longer patterns first, so "American Water Works" wins over a shorter overlap.
        self._patterns = sorted(patterns, key=lambda item: -len(item[1].pattern))

    def find(self, text: str) -> tuple[str, ...]:
        found: dict[str, int] = {}
        for name, pattern in self._patterns:
            match = pattern.search(text)
            if match and name not in found:
                found[name] = match.start()
        return tuple(sorted(found, key=lambda name: found[name]))

    def mask(self, text: str, placeholder: str) -> str:
        """`text` with every company mention replaced by `placeholder`, keeping a possessive."""

        def replace(match: re.Match[str]) -> str:
            mention = match.group(0)
            return placeholder + ("'s" if mention.endswith("'s") else "")

        text = text.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
        for _name, pattern in self._patterns:
            text = pattern.sub(replace, text)
        return text


def understand(question: str, matcher: CompanyMatcher) -> QueryCues:
    """The company, periods and forms a question mentions."""
    text = question.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    quarters: list[tuple[int, int]] = []
    spans: list[tuple[int, int]] = []
    for pattern in _QUARTER_PATTERNS:
        for match in pattern.finditer(text):
            first, second = match.group(1), match.group(2)
            if first.lower() in _ORDINALS:
                quarters.append((_year(second), _ORDINALS[first.lower()]))
            elif len(first) == 4:
                quarters.append((_year(first), int(second)))
            else:
                quarters.append((_year(second), int(first)))
            spans.append(match.span())
    dates = []
    for pattern in _DATES:
        for match in pattern.finditer(text):
            parts = match.groups()
            if parts[0].isdigit():
                day, month, year = int(parts[0]), _MONTHS[parts[1].lower()], int(parts[2])
            else:
                month, day, year = _MONTHS[parts[0].lower()], int(parts[1]), int(parts[2])
            dates.append((year, month, day))
    years = [_year(m.group(1)) for m in _FISCAL_YEAR.finditer(text)]
    years += [int(m.group(1)) for m in _BARE_YEAR.finditer(text)]
    years += [year for year, _ in quarters] + [year for year, _, _ in dates]
    forms = [form for form, pattern in _FORM_PATTERNS if pattern.search(text)]
    return QueryCues(
        companies=matcher.find(text),
        years=tuple(sorted(set(years))),
        quarters=tuple(sorted(set(quarters))),
        dates=tuple(sorted(set(dates))),
        forms=tuple(forms),
        outlook=bool(_OUTLOOK.search(text)),
    )


def _matches_period(filing: Filing, cues: QueryCues) -> bool:
    if not (cues.years or cues.quarters or cues.dates):
        return True
    if filing.date is not None:  # an 8-K: match the date, else the quarter, else the year
        if cues.dates:
            return any(date[:2] == filing.date[:2] for date in cues.dates)
        if cues.quarters:
            return (filing.date[0], (filing.date[1] - 1) // 3 + 1) in cues.quarters
        return filing.date[0] in cues.years
    quarters = {*cues.quarters, *((year, (month - 1) // 3 + 1) for year, month, _ in cues.dates)}
    if filing.form in QUARTERLY and filing.quarter is not None and quarters:
        return (filing.year, filing.quarter) in quarters
    if cues.outlook:
        return filing.year in cues.years or filing.year + 1 in cues.years
    return filing.year in cues.years


def resolve(cues: QueryCues, filings: Sequence[Filing]) -> list[str] | None:
    """The filings to search for these cues, or None to search them all."""
    own = [filing for filing in filings if filing.company in cues.companies]
    if not own:
        return None
    chosen = [filing for filing in own if _matches_period(filing, cues)]
    if cues.forms:
        chosen = [filing for filing in chosen if filing.form in cues.forms] or chosen
    return sorted(filing.doc_name for filing in (chosen or own))
