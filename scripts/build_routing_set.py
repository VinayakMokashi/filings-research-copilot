"""Build eval/routing/queries.jsonl and checksums.json from the seeds and reviewed candidates.

Every candidate needs a verdict, and every seed exactly two accepted paraphrases. The
script refuses to replace an existing set unless --force is given, because the test side
must stay fixed once results exist.

Usage: uv run poe build-routing-set
"""

from __future__ import annotations

import argparse
from collections import Counter

from copilot.eval import routing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--force", action="store_true", help="replace an existing routing set")
    args = parser.parse_args(argv)

    if routing.QUERIES_FILE.exists() and not args.force:
        print(f"{routing.QUERIES_FILE} already exists; use --force only to replace it on purpose.")
        return 1
    queries = routing.build(routing.load_seeds(), routing.load_candidates())
    routing.write_set(queries)

    print(f"Wrote {routing.QUERIES_FILE} and {routing.CHECKSUMS_FILE}: {len(queries)} queries")
    for side in ("dev", "test"):
        counts = Counter(q.route for q in queries if q.split == side)
        listed = ", ".join(f"{route} {counts[route]}" for route in routing.ROUTES)
        print(f"  {side:4} {sum(counts.values()):3}  {listed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
