"""Copy the doc agent's collection from the local Qdrant to Qdrant Cloud (ADR-0031).

Reads the cluster's address and its read-write key from `.env` (`CLOUD_QDRANT_URL`,
`CLOUD_QDRANT_API_KEY`), names no local run ever reads, and prints neither. With
`--snapshot-to BUCKET`, it then takes a snapshot of the copy on the cluster and copies
it to gs://BUCKET/qdrant/ with gcloud, for the restore runbook.

Usage: uv run poe copy-collection                                  (fb_page_bge-small)
       uv run poe copy-collection --snapshot-to filings-research-copilot-backups
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient

from copilot.config import get_settings
from copilot.deploy.gcloud import command, run
from copilot.deploy.qdrant import copy_collection, download_snapshot


class CloudQdrant(BaseSettings):
    """The cluster, from `.env`'s CLOUD_* names."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = Field(validation_alias="CLOUD_QDRANT_URL")
    api_key: SecretStr = Field(validation_alias="CLOUD_QDRANT_API_KEY")


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--collection", default=settings.collection)
    parser.add_argument("--snapshot-to", metavar="BUCKET")
    args = parser.parse_args(argv)

    cloud = CloudQdrant()  # from .env
    key = cloud.api_key.get_secret_value()
    source = QdrantClient(url=settings.qdrant_url, timeout=120)
    target = QdrantClient(url=cloud.url, api_key=key, timeout=120)

    copied = copy_collection(
        source,
        target,
        args.collection,
        progress=lambda n: print(f"  {n:,} points copied", end="\r", flush=True),
    )
    stored = target.count(args.collection, exact=True).count
    print(f"{args.collection}: {copied:,} points copied; the cluster holds {stored:,}")

    if args.snapshot_to:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        local = Path("dist") / f"{args.collection}-{stamp}.snapshot"
        download_snapshot(cloud.url, key, args.collection, local)
        target_uri = f"gs://{args.snapshot_to}/qdrant/{local.name}"
        run(command("storage", "cp", str(local), target_uri))
        print(f"snapshot: {target_uri} ({local.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
