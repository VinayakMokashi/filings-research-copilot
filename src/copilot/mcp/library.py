"""What the MCP server's tools read: the search index, the facts database and the parsed
filing pages, with no model calls (step 6.4).

- `search` finds passages the way the doc agent does, minus its rewrites: dense search over
  page chunks (ADR-0011) inside the filings that a company, year and form pick out, or
  that the query itself names (ADR-0012).
- `financials` reads one company's annual values of one metric from the facts database: the
  figure each 10-K first reported, and the latest filing's figure where it was restated.
- `page` returns one parsed page.

Filing text goes out with its instruction-like sentences replaced by a notice, as it does
into the copilot's own prompts: the client's model reads it too.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from copilot.answer.context import FORM_NAMES, describe
from copilot.answer.injection import neutralise
from copilot.config import Settings
from copilot.facts.database import connect_read_only
from copilot.facts.metrics import METRICS, Metric
from copilot.ingest.corpus import filing_pages
from copilot.retrieval.query import CompanyMatcher, Filing, resolve, understand
from copilot.retrieval.search import Hit, Mode

Form = Literal["10-K", "10-Q", "8-K", "earnings"]
FORMS: dict[str, str] = {"10-K": "10k", "10-Q": "10q", "8-K": "8k", "earnings": "earnings"}
FIGURES = """
    SELECT a.fiscal_year, a.value, a.period_start, a.period_end, a.filed, a.accn,
           a.latest_value
    FROM annual_values AS a JOIN companies AS c USING (cik)
    WHERE c.name = ? AND a.metric = ? AND a.fiscal_year BETWEEN ? AND ?
    ORDER BY a.fiscal_year
"""
SOURCE = (
    "SEC XBRL company facts: each figure as first reported in the 10-K for that fiscal year; "
    "`restated` is the figure in the company's latest filing, where it differs."
)


class LibraryError(Exception):
    """A request the library can't serve; the message tells the caller why, and what to try."""


class Index(Protocol):
    def search(
        self, query: str, mode: Mode, limit: int, doc_names: Sequence[str] | None
    ) -> list[Hit]: ...


class Passage(BaseModel):
    label: str = Field(description="The filing and page, as a citation")
    uri: str = Field(description="The whole page, as a resource")
    doc_name: str
    company: str
    form: str
    year: int = Field(description="The fiscal year the filing covers")
    page: int = Field(description="The PDF page, counting from 1")
    section: str | None
    score: float = Field(description="Cosine similarity to the query")
    text: str


class Passages(BaseModel):
    query: str
    filings: list[str] | None = Field(description="The filings searched; null means all")
    passages: list[Passage]


class Figure(BaseModel):
    fiscal_year: int
    value: float
    period_start: str | None
    period_end: str
    filed: str
    accession: str = Field(description="The 10-K that first reported the figure")
    restated: float | None = Field(
        None, description="The figure in the company's latest filing, when it differs"
    )


class Financials(BaseModel):
    company: str
    ticker: str | None
    metric: str
    label: str
    description: str
    unit: str
    statement: str
    figures: list[Figure]
    source: str = SOURCE


class FilingPage(BaseModel):
    label: str
    doc_name: str
    page: int = Field(description="The PDF page, counting from 1")
    pages: int = Field(description="How many pages the filing has")
    section: str | None
    text: str


def page_uri(doc_name: str, page: int) -> str:
    """The resource of a page, numbered from 1 as in the labels."""
    return f"filing://{doc_name}/{page}"


def find_metric(text: str) -> Metric:
    """The metric named by `text`, its name or its label, in any case."""
    key = _key(text)
    for metric in METRICS:
        if key in (metric.name, _key(metric.label)):
            return metric
    names = ", ".join(metric.name for metric in METRICS)
    raise LibraryError(f"There's no metric called {text!r}. The metrics are: {names}.")


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


class Library:
    """The filings in the index, the facts database and the parsed pages.

    The index is built on first use, since loading its embedding model takes seconds.
    """

    def __init__(
        self,
        filings: Sequence[Filing],
        matcher: CompanyMatcher,
        facts_db: Path,
        pages_dir: Path,
        index: Callable[[], Index],
    ) -> None:
        self.filings = list(filings)
        self.by_name = {filing.doc_name: filing for filing in self.filings}
        self.matcher = matcher
        self.facts_db = facts_db
        self.pages_dir = pages_dir
        self._build_index = index
        self._index: Index | None = None
        self._lock = threading.Lock()

    def index(self) -> Index:
        with self._lock:
            if self._index is None:
                self._index = self._build_index()
            return self._index

    def search(
        self,
        query: str,
        company: str | None = None,
        year: int | None = None,
        form: Form | None = None,
        limit: int = 5,
    ) -> Passages:
        """The `limit` passages closest to `query`, in the filings the filters pick out."""
        query = query.strip()
        if not query:
            raise LibraryError("The query is empty.")
        if company or year is not None or form:
            documents: list[str] | None = self.pick(company, year, form)
        else:
            documents = resolve(understand(query, self.matcher), self.filings)
        try:
            hits = self.index().search(query, "dense", limit, documents)
        except (ResponseHandlingException, UnexpectedResponse, httpx.HTTPError) as exc:
            raise LibraryError(
                f"The search index can't be reached ({type(exc).__name__}); is Qdrant running?"
            ) from exc
        return Passages(query=query, filings=documents, passages=[self.passage(h) for h in hits])

    def pick(self, company: str | None, year: int | None, form: Form | None) -> list[str]:
        """The filings of `company`, for fiscal `year`, of `form`: whichever are given."""
        chosen = self.filings
        if company:
            names = self.matcher.find(company)
            if not names:
                raise LibraryError(
                    f"No company in the filings matches {company!r}. "
                    f"The filings cover: {', '.join(self.indexed_companies())}."
                )
            chosen = [filing for filing in chosen if filing.company in names]
            if not chosen:
                raise LibraryError(
                    f"None of {names[0]}'s filings is in the index; query_financials has its "
                    "annual figures."
                )
        own = chosen
        if year is not None:
            chosen = [filing for filing in chosen if filing.year == year]
        if form:
            chosen = [filing for filing in chosen if filing.form == FORMS[form]]
        if not chosen:
            listed = "; ".join(self.title(filing) for filing in own[:30])
            raise LibraryError(f"No filing matches those filters. There are: {listed}.")
        return sorted(filing.doc_name for filing in chosen)

    def passage(self, hit: Hit) -> Passage:
        page = hit.pages[0]
        filing = self.by_name.get(hit.doc_name)
        text, _ = neutralise(hit.text)
        return Passage(
            label=describe(hit.doc_name, page, self.by_name),
            uri=page_uri(hit.doc_name, page + 1),
            doc_name=hit.doc_name,
            company=filing.company if filing else "",
            form=FORM_NAMES.get(filing.form, filing.form) if filing else "",
            year=filing.year if filing else 0,
            page=page + 1,
            section=hit.section,
            score=round(hit.score, 4),
            text=text,
        )

    def financials(
        self,
        company: str,
        metric: str,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> Financials:
        """`company`'s annual values of `metric`, between the fiscal years given."""
        names = self.matcher.find(company)
        if not names:
            raise LibraryError(
                f"No company matches {company!r}. The facts database covers: "
                f"{', '.join(self.database_companies())}."
            )
        if len(names) > 1:
            raise LibraryError(f"{company!r} names {', '.join(names)}; ask for one at a time.")
        chosen = find_metric(metric)
        with closing(self.facts()) as conn:
            found = conn.execute(
                "SELECT name, ticker FROM companies WHERE name = ?", (names[0],)
            ).fetchone()
            if found is None:
                raise LibraryError(f"{names[0]} isn't in the facts database.")
            rows = conn.execute(
                FIGURES, (names[0], chosen.name, from_year or 0, to_year or 9999)
            ).fetchall()
        return Financials(
            company=found[0],
            ticker=found[1],
            metric=chosen.name,
            label=chosen.label,
            description=chosen.description,
            unit=chosen.unit,
            statement=chosen.statement,
            figures=[_figure(row) for row in rows],
        )

    def page(self, doc_name: str, number: int) -> FilingPage:
        """Page `number`, counting from 1, of the filing `doc_name`."""
        if doc_name not in self.by_name:
            raise LibraryError(f"There's no filing called {doc_name!r} in the index.")
        pages = filing_pages(self.pages_dir, doc_name)
        if pages is None:
            raise LibraryError(f"{doc_name} hasn't been parsed; run `uv run poe parse-corpus`.")
        if not 1 <= number <= len(pages):
            raise LibraryError(f"{doc_name} has pages 1 to {len(pages)}.")
        page = pages[number - 1]
        text, _ = neutralise(page.text)
        return FilingPage(
            label=describe(doc_name, number - 1, self.by_name),
            doc_name=doc_name,
            page=number,
            pages=len(pages),
            section=page.section,
            text=text,
        )

    def catalogue(self) -> list[dict[str, Any]]:
        """Every filing in the index, by company and period."""
        return [
            {
                "doc_name": filing.doc_name,
                "company": filing.company,
                "form": FORM_NAMES.get(filing.form, filing.form),
                "year": filing.year,
                "quarter": filing.quarter,
            }
            for filing in sorted(self.filings, key=lambda f: (f.company, f.year, f.doc_name))
        ]

    def coverage(self) -> list[dict[str, Any]]:
        """Every company in the facts database, with its years and its filings in the index."""
        with closing(self.facts()) as conn:
            rows = conn.execute(
                "SELECT c.name, c.ticker, c.sector, MIN(a.fiscal_year), MAX(a.fiscal_year) "
                "FROM companies AS c LEFT JOIN annual_values AS a USING (cik) "
                "GROUP BY c.cik ORDER BY c.name"
            ).fetchall()
        filed = {
            name: sum(f.company == name for f in self.filings) for name in self.indexed_companies()
        }
        return [
            {
                "company": name,
                "ticker": ticker,
                "sector": sector,
                "fiscal_years": [first, last] if first is not None else None,
                "filings_in_index": filed.get(name, 0),
            }
            for name, ticker, sector, first, last in rows
        ]

    def indexed_companies(self) -> list[str]:
        """The companies with filings in the index."""
        return sorted({filing.company for filing in self.filings})

    def database_companies(self) -> list[str]:
        """The companies in the facts database."""
        with closing(self.facts()) as conn:
            return [name for (name,) in conn.execute("SELECT name FROM companies ORDER BY name")]

    def title(self, filing: Filing) -> str:
        form = FORM_NAMES.get(filing.form, filing.form)
        quarter = f" Q{filing.quarter}" if filing.quarter else ""
        return f"{filing.company} {form} {filing.year}{quarter} ({filing.doc_name})"

    def facts(self) -> sqlite3.Connection:
        try:
            return connect_read_only(self.facts_db)
        except FileNotFoundError as exc:
            raise LibraryError(
                "The facts database hasn't been built; run `uv run poe build-facts`."
            ) from exc


def _figure(row: tuple[Any, ...]) -> Figure:
    year, value, start, end, filed, accession, latest = row
    restated = latest if latest != value else None
    return Figure(
        fiscal_year=year,
        value=value,
        period_start=start,
        period_end=end,
        filed=filed,
        accession=accession,
        restated=restated,
    )


def metrics() -> list[dict[str, str]]:
    """Every metric the facts database holds, with its definition."""
    return [
        {
            "metric": metric.name,
            "label": metric.label,
            "description": metric.description,
            "unit": metric.unit,
            "kind": metric.kind,
            "statement": metric.statement,
        }
        for metric in METRICS
    ]


def build_library(settings: Settings) -> Library:
    """The library over the real index, facts database and pages."""
    # Imported here: the doc agent's module brings in LiteLLM, which takes seconds to load,
    # and a desktop client waits for the server to start.
    from copilot.answer.agent import build_searcher, company_matcher, corpus_filings

    return Library(
        corpus_filings(settings),
        company_matcher(),
        settings.data_dir / "processed" / "facts.db",
        settings.data_dir / "processed" / "pages",
        lambda: build_searcher(settings),
    )
