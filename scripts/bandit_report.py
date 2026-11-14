"""Compare the answer bandit with its randomized fixed arm (step 9.3, ADR-0036).

Reads the bandit's log from Firestore (`bandit-answers`), as the owner, with the copilot's
own gcloud configuration, and keeps a copy under data/processed/bandit/; or reads such a
copy with `--from`. Writes eval/results/bandit-online/<name>/summary.json: counts, means,
intervals, p-values and the decision, with no question or answer text (the log holds
none). The report itself is written by hand from it (docs/eval/bandit-online.md).

Usage:
  uv run poe bandit-report --since 2026-11-16 --until 2026-11-30
  uv run poe bandit-report --from data/processed/bandit/bandit-answers.jsonl --name trial
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.deploy.gcloud import PROJECT, command, run
from copilot.eval.bandit_online import report
from copilot.eval.report import RESULTS_DIR

COLLECTION = "bandit-answers"


def from_firestore(project: str) -> list[dict[str, Any]]:
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials

    token = run(command("auth", "print-access-token"), capture=True)
    client = firestore.Client(project=project, credentials=Credentials(token))  # type: ignore[no-untyped-call]
    documents = client.collection(COLLECTION).stream()
    return [(doc.to_dict() or {}) | {"id": doc.id} for doc in documents]


def day(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--from", dest="source", type=Path, help="a copy of the log (JSON lines)")
    parser.add_argument("--since", type=day, help="first UTC day, YYYY-MM-DD")
    parser.add_argument("--until", type=day, help="the UTC day after the last, YYYY-MM-DD")
    parser.add_argument("--name", default="two-weeks")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.source is not None:
        lines = args.source.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
    else:
        records = from_firestore(args.project)
        copy = get_settings().data_dir / "processed" / "bandit" / f"{COLLECTION}.jsonl"
        copy.parent.mkdir(parents=True, exist_ok=True)
        with copy.open("w", encoding="utf-8", newline="\n") as out:
            for record in records:
                out.write(json.dumps(record, default=str) + "\n")
        print(f"Kept a copy of {len(records)} records in {copy}")

    found = report(records, since=args.since, until=args.until)
    folder = args.results_dir / "bandit-online" / args.name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(
        json.dumps(found, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({key: found[key] for key in ("answers", "retries", "arms")}, indent=2))
    for kind, comparison in found["comparisons"].items():
        print(f"{kind}: {json.dumps(comparison)}")
    print(f"Decision: {json.dumps(found['decision'])}")
    print(f"Wrote {folder / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
