"""Build and open the facts database (ADR-0008).

Tables:

- `companies`: the universe, one row per CIK;
- `filings`: each 10-K and 10-Q, with its fiscal year, fiscal period and period end (the
  fiscal year of a 10-K is derived as `normalise` explains; SEC's own label is kept too);
- `concepts`: the label and definition of every XBRL tag;
- `facts`: every fact from those filings, once per filing that reported it;
- `metrics` and `metric_tags`: canonical metrics and the ranked tags behind each;
- `annual_values`: one value per company, metric and fiscal year, as originally reported.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from copilot.facts.metrics import METRICS, annual_values
from copilot.facts.normalise import filings_from, iter_concepts, iter_facts
from copilot.ingest.universe import Company

DATABASE_FILE = Path("data/processed/facts.db")

SCHEMA = """
CREATE TABLE companies (
    cik INTEGER PRIMARY KEY,
    ticker TEXT,
    name TEXT NOT NULL,
    sec_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    fiscal_year_end TEXT NOT NULL
);
CREATE TABLE filings (
    accn TEXT PRIMARY KEY,
    cik INTEGER NOT NULL REFERENCES companies (cik),
    form TEXT NOT NULL,
    filed TEXT NOT NULL,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    period_end TEXT NOT NULL,
    sec_fiscal_year INTEGER
);
CREATE TABLE concepts (
    taxonomy TEXT NOT NULL,
    tag TEXT NOT NULL,
    label TEXT,
    description TEXT,
    PRIMARY KEY (taxonomy, tag)
);
CREATE TABLE facts (
    cik INTEGER NOT NULL REFERENCES companies (cik),
    taxonomy TEXT NOT NULL,
    tag TEXT NOT NULL,
    unit TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT NOT NULL,
    value REAL NOT NULL,
    accn TEXT NOT NULL REFERENCES filings (accn),
    form TEXT NOT NULL,
    filed TEXT NOT NULL,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    frame TEXT
);
CREATE INDEX facts_by_company_tag ON facts (cik, tag);
CREATE INDEX facts_by_filing ON facts (accn);
CREATE TABLE metrics (
    metric TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('duration', 'instant')),
    unit TEXT NOT NULL,
    statement TEXT NOT NULL,
    pick TEXT NOT NULL CHECK (pick IN ('priority', 'largest'))
);
CREATE TABLE metric_tags (
    metric TEXT NOT NULL REFERENCES metrics (metric),
    priority INTEGER NOT NULL,
    taxonomy TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (metric, priority)
);
CREATE TABLE annual_values (
    cik INTEGER NOT NULL REFERENCES companies (cik),
    metric TEXT NOT NULL REFERENCES metrics (metric),
    fiscal_year INTEGER NOT NULL,
    period_start TEXT,
    period_end TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    tag TEXT NOT NULL,
    accn TEXT NOT NULL REFERENCES filings (accn),
    filed TEXT NOT NULL,
    latest_value REAL NOT NULL,
    latest_accn TEXT NOT NULL,
    PRIMARY KEY (cik, metric, fiscal_year)
);
"""


def build(path: Path, companies: Sequence[Company], facts_dir: Path) -> dict[str, int]:
    """Build the database at `path` from cached company-facts files; returns row counts.

    The database is written to a temporary file and moved into place at the end, so a
    failed build never leaves a half-written database behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.unlink(missing_ok=True)
    conn = sqlite3.connect(partial)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (m.name, m.label, m.description, m.kind, m.unit, m.statement, m.pick)
                for m in METRICS
            ],
        )
        conn.executemany(
            "INSERT INTO metric_tags VALUES (?, ?, 'us-gaap', ?)",
            [(m.name, rank, tag) for m in METRICS for rank, tag in enumerate(m.tags, start=1)],
        )
        concepts: dict[tuple[str, str], tuple[str | None, str | None]] = {}
        for company in companies:
            conn.execute(
                "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?)",
                (
                    company.cik,
                    company.ticker,
                    company.name,
                    company.sec_name,
                    company.sector,
                    company.fiscal_year_end,
                ),
            )
            payload = json.loads((facts_dir / f"CIK{company.cik:010d}.json").read_bytes())
            for concept in iter_concepts(payload):
                concepts.setdefault(
                    (concept.taxonomy, concept.tag), (concept.label, concept.description)
                )
            facts = list(iter_facts(payload))
            filings = filings_from(facts)
            conn.executemany(
                "INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (f.accn, f.cik, f.form, f.filed, f.fiscal_year, f.fp, f.period_end, f.fy)
                    for f in filings.values()
                ],
            )
            conn.executemany(
                "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        f.cik,
                        f.taxonomy,
                        f.tag,
                        f.unit,
                        f.start,
                        f.end,
                        f.value,
                        f.accn,
                        f.form,
                        f.filed,
                        f.fy,
                        f.fp,
                        f.frame,
                    )
                    for f in facts
                ],
            )
            for metric in METRICS:
                conn.executemany(
                    "INSERT INTO annual_values VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            v.cik,
                            v.metric,
                            v.fiscal_year,
                            v.start,
                            v.end,
                            v.value,
                            v.unit,
                            v.tag,
                            v.accn,
                            v.filed,
                            v.latest_value,
                            v.latest_accn,
                        )
                        for v in annual_values(facts, filings, metric)
                    ],
                )
        conn.executemany(
            "INSERT INTO concepts VALUES (?, ?, ?, ?)",
            [(tax, tag, label, desc) for (tax, tag), (label, desc) in sorted(concepts.items())],
        )
        conn.commit()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "companies",
                "filings",
                "concepts",
                "facts",
                "metrics",
                "metric_tags",
                "annual_values",
            )
        }
    finally:
        conn.close()
    partial.replace(path)
    return counts


def connect_read_only(path: Path = DATABASE_FILE) -> sqlite3.Connection:
    """Open the database read-only, so queries can't change it."""
    if not path.is_file():
        raise FileNotFoundError(f"{path} doesn't exist; run `uv run poe build-facts` first.")
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
