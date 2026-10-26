"""Count what the prompt-injection patterns flag in the parsed corpus (step 6.2).

Every parsed page in data/processed/pages/ is checked with `copilot.answer.injection`, the
same check the answer's sources go through. The counts by pattern, and each flagged page's
filing and page number (never its text), go to eval/results/injection/corpus-scan.json.
No model is called.

Usage: uv run poe scan-injections
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.answer.injection import PATTERNS, findings
from copilot.config import get_settings
from copilot.eval.report import RESULTS_DIR
from copilot.ingest.pdf import read_pages


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "injection" / "corpus-scan.json")
    args = parser.parse_args(argv)

    pages_dir = get_settings().data_dir / "processed" / "pages"
    files = sorted(pages_dir.glob("*.jsonl"))
    by_pattern: Counter[str] = Counter()
    flagged: list[dict[str, Any]] = []
    pages = 0
    for path in files:
        for page in read_pages(path):
            pages += 1
            names = sorted({name for name, _, _ in findings(page.text)})
            by_pattern.update(names)
            if names:
                flagged.append({"doc_name": page.doc_name, "page": page.page, "patterns": names})

    result = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "filings": len(files),
        "pages": pages,
        "patterns": list(PATTERNS),
        "flagged_pages": len(flagged),
        "by_pattern": {name: by_pattern.get(name, 0) for name in PATTERNS},
        "flagged": flagged,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{pages} pages in {len(files)} filings; {len(flagged)} flagged. Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
