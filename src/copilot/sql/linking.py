"""Value linking for the data agent: what the schema doesn't tell the model (steps 4.2, 4.3).

The baseline guessed metric names that don't exist (`netProfitMargin`) and queried
companies and years the facts database doesn't hold (ADR-0015). `FactsLinker` gives
text2sql-analyst's table-selection and SQL steps the missing facts, as hints:

- **Companies.** Each company the question names, found by name, short name, ticker or a
  common alias (the matcher from query understanding), as its `companies.name` and CIK,
  with the fiscal years its annual values cover; and the list of every company in the
  database, so a question about another one is declined.
- **Metrics.** Every value `annual_values.metric` takes, with its label, so the SQL says
  `eps_diluted` instead of guessing; and the definitions of measures that combine metrics,
  since the database stores the parts (revenue, operating income), not the ratios.
- **Fiscal years.** `fiscal_year` is the company's own label for its year, values are
  annual and as first reported, and results name companies, not CIKs.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from text2sql.db import connect_readonly
from text2sql.linking import ColumnCatalogue, sql_literal

from copilot.retrieval.query import CompanyMatcher

DEFINITIONS = (
    "Measures that combine metrics: gross margin = gross_profit / revenue; operating margin = "
    "operating_income / revenue; net profit margin = net_income / revenue; free cash flow = "
    "operating_cash_flow - capital_expenditure; current ratio = current_assets / "
    "current_liabilities; quick ratio = (current_assets - inventory) / current_liabilities; "
    "return on assets = net_income / total_assets. A margin or ratio is a fraction unless "
    "the question asks for a percentage."
)
FISCAL_YEARS = (
    "annual_values.fiscal_year is the company's own label for its fiscal year, which can end "
    "in another calendar year. Values are annual and as first reported; latest_value is the "
    "same figure in the company's most recent filing."
)
NAMES = "Name companies in results by companies.name, not by cik."


@dataclass(frozen=True)
class Company:
    cik: int
    name: str
    ticker: str | None
    first_year: int | None
    last_year: int | None


def read_companies(conn: sqlite3.Connection) -> list[Company]:
    """Every company, with the first and last fiscal year of its annual values."""
    rows = conn.execute(
        "SELECT c.cik, c.name, c.ticker, MIN(a.fiscal_year), MAX(a.fiscal_year) "
        "FROM companies AS c LEFT JOIN annual_values AS a USING (cik) "
        "GROUP BY c.cik ORDER BY c.name"
    ).fetchall()
    return [Company(*row) for row in rows]


class FactsLinker:
    """text2sql-analyst's `Linker` for the facts database; see the module docstring."""

    def __init__(self, companies: list[Company], metrics: ColumnCatalogue) -> None:
        self._by_name = {company.name: company for company in companies}
        self._matcher = CompanyMatcher(list(self._by_name), {c.name: c.ticker for c in companies})
        self._all = (
            "The database holds only these companies: "
            + ", ".join(self._by_name)
            + ". Any other company is not in it."
        )
        self._metrics = metrics.hint()

    @classmethod
    def read(cls, db_path: str | Path) -> FactsLinker:
        conn = connect_readonly(db_path)
        try:
            companies = read_companies(conn)
        finally:
            conn.close()
        metrics = ColumnCatalogue.read(
            db_path, "metrics", "metric", "label", name="annual_values.metric"
        )
        return cls(companies, metrics)

    def company_hint(self, name: str) -> str:
        company = self._by_name[name]
        years = (
            f"; its annual values cover fiscal {company.first_year} to {company.last_year}"
            if company.first_year is not None
            else "; it has no annual values"
        )
        return f'"{name}" is companies.name = {sql_literal(name)} (cik {company.cik}){years}.'

    def hints(self, question: str) -> list[str]:
        found = [self.company_hint(name) for name in self._matcher.find(question)]
        return [*found, self._all, self._metrics, DEFINITIONS, FISCAL_YEARS, NAMES]
