"""Copy facts.db into PostgreSQL and set up its read-only role (step 8.4).

Creates the `facts` database with the C collation on the server the admin URL names,
unless it exists; replaces its tables with facts.db's in one transaction; and gives the
`facts_reader` role SELECT on them (`copilot.facts.postgres`). Prints the data agent's
URL with the password masked: set FRC_FACTS_URL to it, password included, in a run's
environment to send the data agent's queries there.

The reader's password comes from the environment variable --reader-password-env names.
Only for a server on this machine (the Compose Postgres) does it default to the role's
name, as the Compose file's own credentials do.

Usage: uv run poe load-facts-postgres                    (the Compose Postgres, 127.0.0.1:5433)
       uv run poe load-facts-postgres --admin-url URL --reader-password-env FACTS_READER_PASSWORD
"""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Sequence
from urllib.parse import urlsplit

from copilot.config import get_settings
from copilot.facts.database import DATABASE_FILE
from copilot.facts.postgres import (
    DATABASE,
    READER,
    create_database,
    database_url,
    grant_reader,
    load,
    reader_url,
)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--admin-url",
        help="a role that may create databases and roles (default: FRC_DATABASE_URL)",
    )
    parser.add_argument("--database", default=DATABASE)
    parser.add_argument("--reader-password-env", default="FRC_FACTS_READER_PASSWORD")
    args = parser.parse_args(argv)

    settings = get_settings()
    admin_url = args.admin_url or settings.database_url
    host = urlsplit(admin_url).hostname or ""
    password = os.environ.get(args.reader_password_env)
    if not password:
        if host not in LOCAL_HOSTS:
            parser.error(f"set {args.reader_password_env} for a server that isn't local")
        password = READER

    facts_db = settings.data_dir / "processed" / DATABASE_FILE.name
    start = time.perf_counter()
    created = create_database(admin_url, args.database)
    print(f"database {args.database}: {'created' if created else 'exists'} (collation C)")
    url = database_url(admin_url, args.database)
    counts = load(facts_db, url)
    for table, n in counts.items():
        print(f"  {table:14} {n:>9,} rows")
    grant_reader(url, password, args.database)
    print(f"role {READER}: SELECT on the facts tables, read-only transactions, 15 s timeout")
    print(f"loaded in {time.perf_counter() - start:.1f} s")
    masked = reader_url(admin_url, "***", args.database)
    print(f"FRC_FACTS_URL={masked}  (with the reader's password in place of ***)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
