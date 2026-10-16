"""Cross-check the facts database against FinanceBench dev answers and write a report.

Writes eval/results/facts/financebench-dev-checks.md and .json.

Usage: uv run poe check-facts   (after `poe build-facts`)
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from copilot.config import get_settings
from copilot.eval.splits import load_split
from copilot.facts import checks
from copilot.facts.database import connect_read_only
from copilot.ingest.universe import read_companies

OUT_DIR = Path("eval/results/facts")


def main() -> int:
    settings = get_settings()
    dev = load_split("dev", settings.data_dir / "raw" / "financebench")
    answers = {question.id: question.answer for question in dev}
    cik_by_company = {company.name: company.cik for company in read_companies()}
    conn = connect_read_only(settings.data_dir / "processed" / "facts.db")
    try:
        results = checks.run_checks(conn, checks.load_checks(), answers, cik_by_company)
    finally:
        conn.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = checks.render_report(results)
    (OUT_DIR / "financebench-dev-checks.md").write_text(report, encoding="utf-8", newline="\n")
    (OUT_DIR / "financebench-dev-checks.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(report)
    print(f"Wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
