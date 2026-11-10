"""The demo database on Cloud SQL (ADR-0031): demo windows, and the facts loaded into it.

- **Demo windows.** `demo-up` starts the instance and waits until Cloud SQL's operation
  ends; `demo-down` stops it the same way. The API's `FactsExecutor` notices within a
  minute either way. A Cloud
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
# A user created through the Cloud SQL API joins cloudsqlsuperuser, which owns the
# database (so it could create schemas and tables), and may create roles and databases.
# The first two lines take all of that away; repeated, the REVOKE only warns.
GRANTS = f"""
REVOKE cloudsqlsuperuser FROM {READER};
ALTER ROLE {READER} NOCREATEDB NOCREATEROLE;
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
    """Start (ALWAYS) or stop (NEVER) the instance; its storage stays either way.

    `--async` returns at once with the operation's name, which `change_activation` waits
    for: gcloud's own wait gives up after about ten minutes, and the first start took ten
    and a half.
    """
    return command(
        "sql", "instances", "patch", INSTANCE, f"--activation-policy={policy}",
        "--async", "--quiet", "--format=value(name)",
    )  # fmt: skip


def describe_state() -> list[str]:
    return command("sql", "instances", "describe", INSTANCE, "--format=value(state)")


def describe_operation(name: str) -> list[str]:
    """An operation's status (PENDING, RUNNING or DONE) and its first error, if any."""
    return command(
        "sql", "operations", "describe", name, "--format=value(status,error.errors[0].message)"
    )


def change_activation(
    policy: Literal["ALWAYS", "NEVER"],
    gcloud: Callable[[list[str]], str],
    *,
    timeout_s: float = 1500.0,  # a start has taken ten and a half minutes
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Start or stop the instance and wait until Cloud SQL's operation ends; returns the
    instance's state then. `gcloud` runs a command line and returns its output.

    The state is no guide while the operation runs: a ten-minute start read RUNNABLE six
    seconds in, then MAINTENANCE, then RUNNABLE again with two and a half minutes to go.
    """
    operation = gcloud(set_activation(policy))
    status = wait_for(
        lambda: gcloud(describe_operation(operation)),
        lambda line: line.split("\t", 1)[0] == "DONE",
        timeout_s=timeout_s,
        sleep=sleep,
        clock=clock,
    )
    if error := status.partition("\t")[2].strip():
        raise RuntimeError(f"Cloud SQL's operation failed: {error}")
    return gcloud(describe_state())


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
    read: Callable[[], str],
    done: Callable[[str], bool],
    *,
    timeout_s: float = 900.0,
    every_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Poll `read` (a state or an operation's status) until `done` accepts it; returns it."""
    deadline = clock() + timeout_s
    while True:
        value = read()
        if done(value):
            return value
        if clock() >= deadline:
            raise TimeoutError(f"still {value.strip() or 'unknown'} after {timeout_s:.0f} s")
        sleep(every_s)
