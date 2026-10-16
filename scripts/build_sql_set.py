"""Build eval/sql/questions.jsonl from eval/sql/source.jsonl by running every gold query.

Each answerable question gets the rows its gold SQL returns from the facts database, and
every question gets its split. The script refuses to replace an existing set unless --force
is given, because the test side must stay fixed once results exist.

Usage: uv run poe build-sql-set   (after `poe build-facts`)
"""

from __future__ import annotations

import argparse
from collections import Counter

from copilot.config import get_settings
from copilot.eval import sql
from copilot.facts.database import connect_read_only


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--force", action="store_true", help="replace an existing SQL set")
    args = parser.parse_args(argv)

    if sql.QUESTIONS_FILE.exists() and not args.force:
        print(f"{sql.QUESTIONS_FILE} already exists; use --force only to replace it on purpose.")
        return 1
    conn = connect_read_only(get_settings().data_dir / "processed" / "facts.db")
    try:
        questions = sql.build(sql.load_source(), conn)
    finally:
        conn.close()
    sql.write_set(questions)

    print(f"Wrote {sql.QUESTIONS_FILE} and {sql.CHECKSUMS_FILE}: {len(questions)} questions")
    for side in ("dev", "test"):
        on_side = [q for q in questions if q.split == side]
        answerable = sum(q.answerable for q in on_side)
        declined = len(on_side) - answerable
        print(f"  {side:4} {len(on_side):3}  answerable {answerable}, unanswerable {declined}")
    print("  categories:", dict(Counter(q.category for q in questions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
