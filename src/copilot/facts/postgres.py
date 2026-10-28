"""The facts tables in PostgreSQL (step 8.4): the same schema and rows as facts.db.

SQLite stays the build target (`copilot.facts.database`). This module copies its tables
into a PostgreSQL database for the deployment, where the data agent's queries run on
a server (ADR-0031):

- **The same schema.** Keys, foreign keys and checks as in SQLite; REAL becomes DOUBLE
  PRECISION, because SQLite's REAL is an 8-byte float and PostgreSQL's has 4 bytes.
  facts.db's references all resolve, so PostgreSQL can enforce them.
- **SQLite's text order.** The database uses the C collation, so `ORDER BY` on text and
  text2sql-analyst's value catalogues sort as SQLite's byte order does.
- **A role that can only read.** `facts_reader` may connect and select, and every
  transaction it starts is read-only, with a statement timeout, as a second layer under
  text2sql-analyst's own read-only connections and guardrails.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from copilot.facts.database import SCHEMA

# facts.db's tables, parents first, so the foreign keys hold while rows arrive.
TABLES = ("companies", "filings", "concepts", "facts", "metrics", "metric_tags", "annual_values")
POSTGRES_SCHEMA = SCHEMA.replace(" REAL", " DOUBLE PRECISION")
DATABASE = "facts"
READER = "facts_reader"


def database_url(url: str, database: str) -> str:
    """The same server and user, another database."""
    return urlunsplit(urlsplit(url)._replace(path=f"/{database}"))


def create_database(admin_url: str, database: str = DATABASE) -> bool:
    """Create the database with the C collation unless it exists; True if it was created."""
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if exists:
            return False
        conn.execute(
            sql.SQL(
                "CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'"
            ).format(sql.Identifier(database))
        )
        return True


def load(sqlite_path: Path, url: str) -> dict[str, int]:
    """Replace the facts tables at `url` with facts.db's, in one transaction.

    Readers see the old tables or the new ones, never a half-loaded set. Returns the rows
    copied per table.
    """
    uri = f"file:{sqlite_path.resolve().as_posix()}?mode=ro"
    counts: dict[str, int] = {}
    with closing(sqlite3.connect(uri, uri=True)) as lite, psycopg.connect(url) as pg:
        with pg.transaction():
            pg.execute(
                sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(t) for t in reversed(TABLES))
                )
            )
            pg.execute(POSTGRES_SCHEMA.encode())
            for table in TABLES:
                columns = [row[1] for row in lite.execute(f'PRAGMA table_info("{table}")')]
                copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
                )
                select = f'SELECT {", ".join(columns)} FROM "{table}"'
                n = 0
                with pg.cursor().copy(copy_sql) as copy:
                    for row in lite.execute(select):
                        copy.write_row(row)
                        n += 1
                counts[table] = n
        pg.execute("ANALYZE")
    return counts


def grant_reader(
    url: str, password: str, database: str = DATABASE, *, role_name: str = READER
) -> None:
    """Create or update the read-only role and give it SELECT on the facts tables only."""
    role = sql.Identifier(role_name)
    db = sql.Identifier(database)
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,)).fetchone()
        # Utility statements take no bind parameters, so the password is quoted client-side.
        verb = "ALTER" if exists else "CREATE"
        conn.execute(
            sql.SQL(verb + " ROLE {} LOGIN PASSWORD {} CONNECTION LIMIT 20").format(
                role, sql.Literal(password)
            )
        )
        for setting, value in (
            ("default_transaction_read_only", "on"),
            ("statement_timeout", "15s"),
            ("idle_in_transaction_session_timeout", "30s"),
        ):
            conn.execute(
                sql.SQL("ALTER ROLE {} SET {} = {}").format(
                    role, sql.Identifier(setting), sql.Literal(value)
                )
            )
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, role))
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(role))
        # Tables the loader recreates later are readable too, without granting again.
        default = "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}"
        conn.execute(sql.SQL(default).format(role))


def reader_url(
    admin_url: str, password: str, database: str = DATABASE, *, role_name: str = READER
) -> str:
    """The URL the data agent uses: the reader role on the facts database, and a short
    connect timeout, so a stopped server hands over to the file quickly."""
    parts = urlsplit(database_url(admin_url, database))
    host = parts.netloc.rsplit("@", 1)[-1]
    netloc = f"{role_name}:{password}@{host}"
    return urlunsplit(parts._replace(netloc=netloc, query="connect_timeout=2"))
