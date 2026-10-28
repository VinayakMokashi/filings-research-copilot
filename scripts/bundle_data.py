"""Build the data bundle the API image carries on Cloud Run (ADR-0031), and upload it.

`copilot.deploy.bundle` says what the bundle holds. The archive is written to
dist/api-data.tar.gz. infra/data-bundle.json records the object the images are built
from, `api-data-<first 12 hex of the hash>.tar.gz`, with its SHA-256 and size. CI
downloads that object from the data bucket and checks the hash before it builds.

Usage: uv run poe bundle-data                       (build; prints the upload command)
       uv run poe bundle-data --upload BUCKET      (and copy it to gs://BUCKET with gcloud)
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from copilot.config import get_settings
from copilot.deploy.bundle import build
from copilot.deploy.gcloud import command, run

OUT = Path("dist/api-data.tar.gz")
POINTER = Path("infra/data-bundle.json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--upload", metavar="BUCKET", help="copy the bundle to gs://BUCKET")
    args = parser.parse_args(argv)

    digest, size, count = build(OUT, get_settings())
    name = f"api-data-{digest[:12]}.tar.gz"
    POINTER.parent.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(
        json.dumps({"object": name, "sha256": digest, "bytes": size, "files": count}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"{OUT}: {count} files, {size / 1e6:.1f} MB, sha256 {digest}")
    print(f"{POINTER}: images build from {name}")
    target = f"gs://{args.upload or '<data bucket>'}/{name}"
    upload = command("storage", "cp", str(OUT), target, "--no-clobber")
    if args.upload:
        run(upload)  # the project's own gcloud configuration, never the active one
        print(f"uploaded to {target}")
    else:
        print("upload: gcloud " + " ".join(upload[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
