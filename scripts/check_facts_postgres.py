"""Run the data agent's evaluated queries on facts.db and on PostgreSQL, and compare
the results (step 8.4).

The queries are the SQL set's gold queries and every query the data agent wrote in the
SQL set's runs (eval/results/sql/<run>/<split>/trace.jsonl). When the local answers
exist, they also include the queries it wrote for FinanceBench's dev figure questions
(data/processed/answers/<run>/dev/answers.jsonl, git-ignored). Each one runs through
text2sql-analyst's executor on both databases, translated from SQLite's dialect for
PostgreSQL. The results must have the same columns and the same rows in the same order,
with floats bit for bit or within 1e-9.

The summary and one line per query go to eval/results/facts/postgres-equivalence/,
with ids and outcomes only; no query from a FinanceBench run is written.

Usage: uv run poe load-facts-postgres, then, with FRC_FACTS_URL set to the reader URL it
       prints (password included) in the environment: uv run poe check-facts-postgres
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from text2sql.execution import QueryError, QueryResult, execute_query

from copilot.config import get_settings
from copilot.eval.report import RESULTS_DIR
from copilot.facts.database import DATABASE_FILE

SQL_SET = Path("eval/sql/questions.jsonl")
SQL_RUNS = RESULTS_DIR / "sql"
OUT = RESULTS_DIR / "facts" / "postgres-equivalence"


@dataclass
class Query:
    sql: str
    uses: list[tuple[str, str]] = field(default_factory=list)  # (source, id)


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def collect(answers_dir: Path) -> dict[str, Query]:
    """Every distinct query, with where it was used."""
    queries: dict[str, Query] = {}

    def add(sql: str | None, source: str, item_id: str) -> None:
        if sql and sql.strip():
            queries.setdefault(sql, Query(sql)).uses.append((source, item_id))

    for item in _jsonl(SQL_SET):
        add(item.get("gold_sql"), "sql-set/gold", item["id"])
    for trace in sorted(SQL_RUNS.glob("*/*/trace.jsonl")):
        source = f"sql-set/{trace.parent.parent.name}/{trace.parent.name}"
        for item in _jsonl(trace):
            add(item.get("sql"), source, item["id"])
    for answers in sorted(answers_dir.glob("data-agent-*/dev/answers.jsonl")):
        source = f"financebench/{answers.parent.parent.name}"
        for item in _jsonl(answers):
            add((item.get("data") or {}).get("sql"), source, item["id"])
    return queries


def _run(target: str | Path, sql: str) -> QueryResult | QueryError:
    try:
        return execute_query(target, sql)
    except QueryError as exc:
        return exc


def _same_value(a: Any, b: Any) -> tuple[bool, bool]:
    """(equal, bit for bit)."""
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return False, False
        if float(a) == float(b):
            return True, True
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12), False
    return a == b, a == b


def compare(lite: QueryResult | QueryError, pg: QueryResult | QueryError) -> str:
    if isinstance(lite, QueryError) or isinstance(pg, QueryError):
        if isinstance(lite, QueryError) and isinstance(pg, QueryError):
            return "error on both"
        if isinstance(lite, QueryError):
            return "error on SQLite only"
        return "error on PostgreSQL only"
    if lite.columns != pg.columns:
        return "different columns"
    if len(lite.rows) != len(pg.rows) or lite.truncated != pg.truncated:
        return "different rows"
    in_order = _rows_match(lite.rows, pg.rows)
    if in_order is not None:
        return in_order
    # A query that leaves the order open (no ORDER BY, or ties in it) may list the same
    # rows in another order on each engine.
    if _rows_match(sorted(lite.rows, key=repr), sorted(pg.rows, key=repr)) is not None:
        return "same rows, another order"
    return "different rows"


def _rows_match(lite_rows: Sequence[Sequence[Any]], pg_rows: Sequence[Sequence[Any]]) -> str | None:
    """ "identical", "equal within 1e-9", or None when some value differs."""
    exact = True
    for lite_row, pg_row in zip(lite_rows, pg_rows, strict=True):
        for a, b in zip(lite_row, pg_row, strict=True):
            equal, bitwise = _same_value(a, b)
            if not equal:
                return None
            exact = exact and bitwise
    return "identical" if exact else "equal within 1e-9"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.facts_url is None:
        parser.error("set FRC_FACTS_URL to the facts database's reader URL")
    url = settings.facts_url.get_secret_value()
    facts_db = settings.data_dir / "processed" / DATABASE_FILE.name
    queries = collect(settings.data_dir / "processed" / "answers")

    items: list[dict[str, Any]] = []
    by_query: Counter[str] = Counter()
    times: dict[str, list[float]] = {"sqlite": [], "postgres": []}
    for query in queries.values():
        lite = _run(facts_db, query.sql)
        pg = _run(url, query.sql)
        outcome = compare(lite, pg)
        by_query[outcome] += 1
        for engine, result in (("sqlite", lite), ("postgres", pg)):
            if isinstance(result, QueryResult):
                times[engine].append(result.elapsed_s)
        for source, item_id in query.uses:
            # Errors are kept for the project's own SQL set only: a message can quote a
            # FinanceBench run's query.
            error = pg if isinstance(pg, QueryError) else lite
            items.append(
                {
                    "source": source,
                    "id": item_id,
                    "outcome": outcome,
                    "rows": len(lite.rows) if isinstance(lite, QueryResult) else None,
                    "error": str(error)
                    if isinstance(error, QueryError) and source.startswith("sql-set/")
                    else None,
                }
            )

    by_outcome = Counter(item["outcome"] for item in items)
    summary = {
        "queries": len(queries),
        "uses": len(items),
        "outcomes_by_query": dict(sorted(by_query.items())),
        "outcomes_by_use": dict(sorted(by_outcome.items())),
        "by_source": {
            source: dict(sorted(Counter(i["outcome"] for i in uses).items()))
            for source in sorted({i["source"] for i in items})
            for uses in [[i for i in items if i["source"] == source]]
        },
        "median_ms": {
            engine: round(statistics.median(values) * 1000, 2) if values else None
            for engine, values in times.items()
        },
        "postgres_url": "facts_reader@<host>/facts",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (args.out / "items.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for item in sorted(items, key=lambda i: (i["source"], i["id"])):
            f.write(json.dumps(item, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))
    same = {"identical", "equal within 1e-9", "same rows, another order", "error on both"}
    return 0 if set(by_outcome) <= same else 1


if __name__ == "__main__":
    raise SystemExit(main())
