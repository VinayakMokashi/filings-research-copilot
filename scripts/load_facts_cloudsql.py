"""Load the facts tables into the demo database on Cloud SQL (step 8.4, ADR-0031).

Run it after `poe load-facts-postgres` (the local copy) and `poe demo-up` (the instance
running). It:

1. dumps the local `facts` database with pg_dump in the Compose container, with DROP
   statements so a reload replaces the tables, to dist/facts.sql.gz;
2. copies the dump to gs://filings-research-copilot-backups/sql/ and imports it as the
   `postgres` user;
3. creates the `facts_reader` user with a generated password, unless the `facts-url`
   secret already exists (`--rotate` makes a new password), and grants it SELECT on the
   facts tables;
4. puts the reader's URL, on the instance's private address, into the `facts-url`
   secret; the API reads it at start.

No password is printed. A secret goes to gcloud on its standard input. gcloud takes a
user's password only as an argument, of a local process.

Usage: uv run poe load-facts-cloudsql [--rotate]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from copilot.deploy.cloudsql import (
    GRANTS,
    INSTANCE,
    import_sql,
    new_password,
    private_address,
    reader_url,
)
from copilot.deploy.gcloud import PROJECT, command, run
from copilot.facts.postgres import DATABASE, READER

BUCKET = f"{PROJECT}-backups"
DUMP = Path("dist/facts.sql.gz")
GRANTS_FILE = Path("dist/facts-grants.sql")


def dump(out: Path) -> str:
    """pg_dump the local facts database, gzipped as it streams; returns its SHA-256."""
    out.parent.mkdir(parents=True, exist_ok=True)
    pg_dump = [
        "docker", "compose", "exec", "-T", "postgres", "pg_dump", "-U", "copilot",
        "-d", DATABASE, "--no-owner", "--no-acl", "--clean", "--if-exists",
    ]  # fmt: skip
    digest = hashlib.sha256()
    with subprocess.Popen(pg_dump, stdout=subprocess.PIPE) as process:
        assert process.stdout is not None
        with gzip.GzipFile(out, mode="wb", mtime=0) as gz:
            for chunk in iter(lambda: process.stdout.read(1 << 20), b""):  # type: ignore[union-attr]
                gz.write(chunk)
                digest.update(chunk)
    if process.returncode != 0:
        raise SystemExit(f"pg_dump failed ({process.returncode})")
    return digest.hexdigest()


def has_version(secret: str) -> bool:
    try:
        run(
            command("secrets", "versions", "describe", "latest", f"--secret={secret}"),
            capture=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def upload(local: Path, name: str) -> str:
    uri = f"gs://{BUCKET}/sql/{name}"
    run(command("storage", "cp", str(local), uri, "--no-clobber"))
    return uri


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--rotate", action="store_true", help="give the reader a new password")
    args = parser.parse_args(argv)
    if shutil.which("docker") is None:
        raise SystemExit("needs Docker, for pg_dump in the Compose container")

    digest = dump(DUMP)
    uri = upload(DUMP, f"facts-{digest[:12]}.sql.gz")
    run(import_sql(uri))
    print(f"imported {uri} into {INSTANCE}/{DATABASE}")

    if args.rotate or not has_version("facts-url"):
        password = new_password()
        users = run(
            command("sql", "users", "list", f"--instance={INSTANCE}", "--format=value(name)"),
            capture=True,
        ).split()
        verb = "set-password" if READER in users else "create"
        run(
            command(
                "sql", "users", verb, READER, f"--instance={INSTANCE}", f"--password={password}"
            )
        )
        address = run(private_address(), capture=True)
        run(
            command("secrets", "versions", "add", "facts-url", "--data-file=-"),
            stdin=reader_url(address, password),
        )
        print(f"{READER}: {verb} done; a new version of facts-url holds its URL")
    else:
        print(f"{READER}: kept its password (--rotate makes a new one)")

    GRANTS_FILE.write_text(GRANTS, encoding="utf-8", newline="\n")
    grants = hashlib.sha256(GRANTS.encode()).hexdigest()[:12]
    run(import_sql(upload(GRANTS_FILE, f"facts-grants-{grants}.sql")))
    print(f"{READER}: SELECT on the facts tables, read-only transactions, 15 s timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
