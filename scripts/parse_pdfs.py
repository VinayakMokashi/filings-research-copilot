"""Parse the FinanceBench PDFs into clean, section-tagged page text (ADR-0009).

Writes data/processed/pages/<doc_name>.jsonl and a manifest. A rerun parses only new or
changed PDFs, or every PDF after a parser change.

Usage: uv run poe parse-pdfs   (after `poe fetch-financebench`)
"""

from __future__ import annotations

import argparse
import time

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.ingest.corpus import manifest_summary, parse_corpus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--workers", type=int, default=8, help="parallel worker processes")
    args = parser.parse_args(argv)

    settings = get_settings()
    root = settings.data_dir / "raw" / "financebench"
    out_dir = settings.data_dir / "processed" / "pages"
    started = time.perf_counter()
    report = parse_corpus(root / "pdfs", out_dir, fb.load_documents(root), workers=args.workers)
    elapsed = time.perf_counter() - started

    summary = manifest_summary(report.manifest)
    print(
        f"Parsed {report.parsed} PDFs and skipped {report.skipped} up to date, in {elapsed:.0f} s"
    )
    documents, pages, empty = summary["documents"], summary["pages"], summary["empty_pages"]
    print(f"  {documents} documents, {pages:,} pages, {empty} empty")
    if summary["ten_k_pages"]:
        share = summary["ten_k_sectioned_pages"] / summary["ten_k_pages"]
        print(f"  10-K pages with a section: {share:.0%}")
    print(f"Wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
