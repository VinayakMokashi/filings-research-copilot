"""Build data/processed/facts.db from the cached SEC company facts (ADR-0008).

Usage: uv run poe build-facts   (after `poe fetch-sec`)
"""

from __future__ import annotations

import sqlite3

from copilot.config import get_settings
from copilot.facts import database
from copilot.ingest.universe import read_companies

YEARS = range(2015, 2024)  # the fiscal years FinanceBench's documents cover most


def main() -> int:
    settings = get_settings()
    path = settings.data_dir / "processed" / "facts.db"
    counts = database.build(
        path, read_companies(), settings.data_dir / "raw" / "sec" / "companyfacts"
    )
    print(f"Built {path} ({path.stat().st_size / 1e6:.0f} MB)")
    for table, count in counts.items():
        print(f"  {table:14} {count:>9,}")

    conn = sqlite3.connect(path)
    possible = counts["companies"] * len(YEARS)
    print(f"\nAnnual-value coverage, FY{YEARS[0]} to FY{YEARS[-1]} (of {possible} company-years):")
    coverage = conn.execute(
        "SELECT metric, COUNT(*) FROM annual_values WHERE fiscal_year BETWEEN ? AND ? "
        "GROUP BY metric ORDER BY metric",
        (YEARS[0], YEARS[-1]),
    ).fetchall()
    for metric, n in coverage:
        print(f"  {metric:32} {n:4}  {n / possible:5.0%}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
