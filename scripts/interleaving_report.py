"""Count the search page's interleaving (step 9.4, ADR-0038).

Reads the searches and their clicks from Firestore (`interleaving`), as the owner, with the
copilot's own gcloud configuration, and keeps a copy under data/processed/interleaving/; or
reads such a copy with `--from`. Writes eval/results/interleaving/<name>/summary.json:
searches, clicks and wins by ranking, and the sign test's p-value. No query is stored
anywhere, so none is read.

Usage:
  uv run poe interleaving-report
  uv run poe interleaving-report --from data/processed/interleaving/interleaving.jsonl --name trial
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.deploy.gcloud import PROJECT, command, run
from copilot.eval.interleaving import tally
from copilot.eval.report import RESULTS_DIR

COLLECTION = "interleaving"


def from_firestore(project: str) -> list[dict[str, Any]]:
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials

    token = run(command("auth", "print-access-token"), capture=True)
    client = firestore.Client(project=project, credentials=Credentials(token))  # type: ignore[no-untyped-call]
    documents = client.collection(COLLECTION).stream()
    return [(doc.to_dict() or {}) | {"id": doc.id} for doc in documents]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--from", dest="source", type=Path, help="a copy (JSON lines)")
    parser.add_argument("--name", default="to-date")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.source is not None:
        lines = args.source.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
    else:
        records = from_firestore(args.project)
        copy = get_settings().data_dir / "processed" / "interleaving" / f"{COLLECTION}.jsonl"
        copy.parent.mkdir(parents=True, exist_ok=True)
        with copy.open("w", encoding="utf-8", newline="\n") as out:
            for record in records:
                out.write(json.dumps(record, default=str) + "\n")
        print(f"Kept a copy of {len(records)} searches in {copy}")

    found = tally(records)
    folder = args.results_dir / "interleaving" / args.name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(
        json.dumps(found, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(found, indent=2))
    print(f"Wrote {folder / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
