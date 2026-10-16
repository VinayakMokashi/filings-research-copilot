"""Download FinanceBench into data/raw/financebench and verify every file.

Usage:
  uv run poe fetch-financebench                     # question files and the referenced PDFs
  uv run poe fetch-financebench --pdfs all          # every PDF in the repository (about 705 MB)
  uv run poe fetch-financebench --pdfs none         # question files only
  uv run poe fetch-financebench --refresh-manifest  # rebuild the committed manifest from GitHub
"""

from __future__ import annotations

import argparse
import hashlib
from typing import cast

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.http import make_client
from copilot.logs import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--pdfs", choices=("referenced", "all", "none"), default="referenced")
    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help=f"list the pinned commit's files and write {fb.MANIFEST_FILE}",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "raw" / "financebench"

    with make_client() as client:
        if args.refresh_manifest:
            manifest = fb.build_manifest(client)
            fb.save_manifest(manifest)
            print(f"Wrote {fb.MANIFEST_FILE}: {len(manifest.files)} files at {manifest.commit}.")
            return 0
        report = fb.fetch(client, root, fb.load_manifest(), cast(fb.PdfSelection, args.pdfs))

    print(f"{report.downloaded} downloaded and {report.already_present} already verified in {root}")
    for path in (fb.QUESTIONS_PATH, fb.DOCUMENTS_PATH):
        digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
        print(f"  sha256 {digest}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
