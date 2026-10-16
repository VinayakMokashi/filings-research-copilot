"""Match FinanceBench's companies to SEC filers and download their XBRL company facts.

Writes data/reference/companies.csv (the universe) and data/reference/sec_manifest.json
(what was downloaded, when, and its checksum), and caches the raw JSON under
data/raw/sec/. Files already cached are reused unless --refresh is given.

Usage: uv run poe fetch-sec   (needs SEC_USER_AGENT in .env and FinanceBench fetched)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.ingest import sec
from copilot.ingest.universe import COMPANIES_FILE, Company, match_companies, write_companies
from copilot.logs import configure_logging

MANIFEST_FILE = Path("data/reference/sec_manifest.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--refresh", action="store_true", help="download again even if cached")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    raw = settings.data_dir / "raw" / "sec"
    documents = fb.load_documents(settings.data_dir / "raw" / "financebench").values()
    sectors: dict[str, Counter[str]] = {}
    for document in documents:
        sectors.setdefault(document.company, Counter())[document.gics_sector] += 1

    downloads: list[sec.Download] = []
    companies: list[Company] = []
    with sec.SecClient(settings.sec_user_agent) as client:
        listing = sec.fetch_cached(
            client, sec.TICKERS_URL, raw / "company_tickers.json", refresh=args.refresh
        )
        downloads.append(listing)
        tickers = sec.parse_tickers(json.loads(listing.path.read_bytes()))
        for match in match_companies(sectors, tickers):
            submissions = sec.fetch_cached(
                client,
                sec.SUBMISSIONS_URL.format(cik=match.cik),
                raw / "submissions" / f"CIK{match.cik:010d}.json",
                refresh=args.refresh,
            )
            facts = sec.fetch_cached(
                client,
                sec.COMPANY_FACTS_URL.format(cik=match.cik),
                raw / "companyfacts" / f"CIK{match.cik:010d}.json",
                refresh=args.refresh,
            )
            downloads += [submissions, facts]
            record = json.loads(submissions.path.read_bytes())
            companies.append(
                Company(
                    name=match.name,
                    cik=match.cik,
                    ticker=match.ticker,
                    sec_name=record["name"],
                    sector=sectors[match.name].most_common(1)[0][0],
                    fiscal_year_end=record["fiscalYearEnd"],
                    matched_by=match.matched_by,
                )
            )

    write_companies(companies)
    manifest = {
        "note": (
            "Paths are relative to the data directory (data/ by default). Requests carried "
            "the declared SEC_USER_AGENT contact, which is not recorded here."
        ),
        "files": [
            {
                "url": d.url,
                "file": d.path.relative_to(settings.data_dir).as_posix(),
                "fetched_at": d.fetched_at.isoformat(timespec="seconds"),
                "size": d.size,
                "sha256": d.sha256,
            }
            for d in downloads
        ],
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    fetched = sum(d.downloaded for d in downloads)
    print(
        f"{len(companies)} companies; {fetched} files downloaded, {len(downloads) - fetched} cached"
    )
    print(f"Wrote {COMPANIES_FILE} and {MANIFEST_FILE}")
    for company in companies:
        print(
            f"  {company.name:22} {company.ticker or '-':6} CIK {company.cik:<8} "
            f"FYE {company.fiscal_year_end}  {company.matched_by:15} {company.sec_name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
