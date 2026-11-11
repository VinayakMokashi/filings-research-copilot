"""Choose the nightly evaluation's slice of FinanceBench dev questions (step 9.1, ADR-0034).

Draws a fixed number of dev questions from copilot v2's dev run, in proportion to each
route it took and each question type, with a fixed seed, and writes their ids to
eval/nightly/slice.json. The file holds ids only, so it is committed; the nightly run
answers the same questions every night until the slice is chosen again.

Usage: uv run poe nightly-slice [--size 40]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from copilot.eval.nightly import SLICE_SEED, SLICE_SIZE, choose_slice
from copilot.eval.report import RESULTS_DIR, read_rows

SOURCE = Path("copilot") / "copilot-v2" / "dev"
SLICE_FILE = Path("eval") / "nightly" / "slice.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--size", type=int, default=SLICE_SIZE)
    parser.add_argument("--seed", type=int, default=SLICE_SEED)
    parser.add_argument("--out", type=Path, default=SLICE_FILE)
    args = parser.parse_args(argv)

    rows = read_rows(RESULTS_DIR / SOURCE)
    ids = choose_slice(rows, args.size, args.seed)
    chosen = [row for row in rows if row["id"] in set(ids)]
    strata = Counter(f"{row['route']}/{row['question_type']}" for row in chosen)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "source": f"eval/results/{SOURCE.as_posix()}",
                "strata": "route/question_type",
                "size": len(ids),
                "seed": args.seed,
                "counts": dict(sorted(strata.items())),
                "ids": ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(ids)} of {len(rows)} questions: {dict(sorted(strata.items()))}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
