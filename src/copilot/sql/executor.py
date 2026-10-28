"""Where the data agent's queries run (step 8.4, ADR-0031).

With a PostgreSQL URL set (`FRC_FACTS_URL`), the queries run on the server, and on the
SQLite file while the server can't be reached: the deployment's database runs only for
demos (ADR-0016), and facts.db ships with the API. text2sql-analyst translates each
query from SQLite's dialect, so the model's prompts, and the evaluations behind them,
stay as they were.

SQLite's own parser still decides what is valid. A query is compiled on facts.db first
(`EXPLAIN`, which runs nothing), and only one SQLite accepts goes to the server.
sqlglot's parser is more forgiving: on the SQL set's dev questions it moved a JOIN the
model had written after WHERE into place, so PostgreSQL ran a query SQLite rejects and
the agent skipped the repair it makes on SQLite. With the check, a rejected query comes
back with SQLite's own message, and the agent repairs it as before.

A failed connection marks the server as down for a minute, so a stopped database costs
one short connect timeout a minute rather than one per query.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from text2sql.db import DatabaseUnavailableError, connect_readonly
from text2sql.execution import QueryResult, SQLExecutionError, execute_query, validate_sql

from copilot.logs import get_logger

log = get_logger(__name__)


def check_with_sqlite(path: Path, sql: str, dialect: str = "sqlite") -> None:
    """Compile `sql` on the SQLite file without running it; raise what SQLite raises."""
    safe_sql = validate_sql(sql, dialect)
    conn = connect_readonly(path)
    try:
        conn.execute(f"EXPLAIN {safe_sql}")
    except sqlite3.Error as exc:
        raise SQLExecutionError(str(exc)) from exc
    finally:
        conn.close()


class FactsExecutor:
    """Runs one query on PostgreSQL when it is up, and on facts.db otherwise."""

    def __init__(
        self,
        url: str,
        path: Path,
        *,
        retry_after_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = url
        self._path = path
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = float("-inf")

    @property
    def server_up(self) -> bool:
        """False for a minute after the server last failed to connect."""
        return self._clock() >= self._down_until

    def __call__(self, sql: str, max_rows: int, timeout_s: float, dialect: str) -> QueryResult:
        if self.server_up:
            check_with_sqlite(self._path, sql, dialect)
            try:
                return execute_query(self._url, sql, max_rows, timeout_s, dialect)
            except DatabaseUnavailableError:
                self._down_until = self._clock() + self._retry_after_s
                log.warning(
                    "facts_server_unavailable",
                    fallback=self._path.name,
                    retry_after_s=self._retry_after_s,
                )
        return execute_query(self._path, sql, max_rows, timeout_s, dialect)
