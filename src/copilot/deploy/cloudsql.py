"""The demo database on Cloud SQL (ADR-0031): demo windows, and the facts loaded into it.

- **Demo windows.** `demo-up` starts the instance and waits until it runs; `demo-down`
  stops it. The API's `FactsExecutor` notices within a minute either way. A Cloud
  Scheduler job stops the instance every night whatever was left running, and an alert
  fires after four hours up.
- **Loading the facts.** The local PostgreSQL copy (`poe load-facts-postgres`) is dumped,
  copied to the backups bucket and imported with `gcloud sql import`. Cloud SQL has only
  a private address, so nothing connects to it from outside Google's network. The
  `facts_reader` user is created with a generated password, given SELECT on the facts
  tables, and its URL, with the instance's private address, goes straight into the
  `facts-url` secret. No password is printed.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from typing import Literal
from urllib.parse import quote

from copilot.deploy.gcloud import command
from copilot.facts.postgres import READER

INSTANCE = "facts"
DATABASE = "facts"

# Given to the reader once the tables exist; the dump's --no-acl leaves grants out.
GRANTS = f"""
ALTER ROLE {READER} CONNECTION LIMIT 20;
ALTER ROLE {READER} SET default_transaction_read_only = on;
ALTER ROLE {READER} SET statement_timeout = '15s';
ALTER ROLE {READER} SET idle_in_transaction_session_timeout = '30s';
REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC;
GRANT CONNECT ON DATABASE {DATABASE} TO {READER};
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO {READER};
GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {READER};
"""


def set_activation(policy: Literal["ALWAYS", "NEVER"]) -> list[str]:
    """Start (ALWAYS) or stop (NEVER) the instance; its storage stays either way."""
    return command(
        "sql", "instances", "patch", INSTANCE, f"--activation-policy={policy}", "--quiet"
    )


def describe_state() -> list[str]:
    return command("sql", "instances", "describe", INSTANCE, "--format=value(state)")


def private_address() -> list[str]:
    return command(
        "sql",
        "instances",
        "describe",
        INSTANCE,
        "--format=value(ipAddresses[0].ipAddress)",
    )


def import_sql(uri: str) -> list[str]:
    return command(
        "sql", "import", "sql", INSTANCE, uri,
        f"--database={DATABASE}", "--user=postgres", "--quiet",
    )  # fmt: skip


def new_password() -> str:
    return secrets.token_urlsafe(24)


def reader_url(address: str, password: str) -> str:
    """The reader's URL on the private address: TLS required, a short connect timeout."""
    return (
        f"postgresql://{READER}:{quote(password, safe='')}@{address}:5432/{DATABASE}"
        "?sslmode=require&connect_timeout=2"
    )


def wait_for(
    read_state: Callable[[], str],
    done: Callable[[str], bool],
    *,
    timeout_s: float = 900.0,
    every_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Poll the instance's state until `done` accepts it; returns that state."""
    deadline = clock() + timeout_s
    while True:
        state = read_state()
        if done(state):
            return state
        if clock() >= deadline:
            raise TimeoutError(f"the instance is still {state or 'unknown'}")
        sleep(every_s)
