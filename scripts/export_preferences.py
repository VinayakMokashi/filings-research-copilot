"""Export preference pairs for preference tuning (step 9.2, ADR-0035).

Reads the ratings and picks the deployment keeps in Firestore (`feedback`, `preferences`),
as the owner, with the copilot's own gcloud configuration, and writes them as they are to
<out>/firestore/ too. With `--from DIR` it reads such a copy instead. With `--runs`, it also
takes the validator's revisions from local evaluation runs of the copilot
(data/processed/answers/<run>/dev/answers.jsonl and its -drafts run).

Writes, under data/ (git-ignored: a rated question is a visitor's, and a run's are
FinanceBench's, which is never published):

- <out>/pairs.jsonl: TRL's conversational preference format, `prompt`, `chosen` and
  `rejected`, one pair a line;
- <out>/pairs-meta.jsonl: each pair's source, labeller, ids and prompt kind, in the same
  order.

Usage:
  uv run poe export-preferences
  uv run poe export-preferences --runs copilot-v2-cerebras
  uv run poe export-preferences --from data/processed/preferences/firestore
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.deploy.gcloud import PROJECT, command, run
from copilot.eval.preferences import (
    Pair,
    exchange_validator_pairs,
    rating_pairs,
    retry_pairs,
    run_validator_pairs,
)
from copilot.eval.splits import load_split

COLLECTIONS = ("feedback", "preferences")
JSON_FIELDS = ("exchange", "first", "second")  # kept as JSON text in Firestore


def from_firestore(project: str) -> dict[str, list[dict[str, Any]]]:
    """Every document of the two collections, as the owner (gcloud's `frc` configuration)."""
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials

    token = run(command("auth", "print-access-token"), capture=True)
    client = firestore.Client(project=project, credentials=Credentials(token))  # type: ignore[no-untyped-call]
    return {
        name: [(doc.to_dict() or {}) | {"id": doc.id} for doc in client.collection(name).stream()]
        for name in COLLECTIONS
    }


def read_copy(folder: Path) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for name in COLLECTIONS:
        path = folder / f"{name}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        found[name] = [json.loads(line) for line in lines if line.strip()]
    return found


def write_copy(documents: dict[str, list[dict[str, Any]]], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, docs in documents.items():
        with (folder / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as out:
            for doc in docs:
                out.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")


def decoded(doc: dict[str, Any]) -> dict[str, Any]:
    """A document with its JSON-text fields read back."""
    return doc | {
        key: json.loads(doc[key]) if isinstance(doc.get(key), str) else doc.get(key)
        for key in JSON_FIELDS
        if key in doc
    }


def records(path: Path) -> dict[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    found = {}
    for line in lines:
        if line.strip():
            record = json.loads(line)
            found[str(record["id"])] = record
    return found


def run_pairs(runs: Sequence[str], data_dir: Path) -> list[Pair]:
    answers_root = data_dir / "processed" / "answers"
    questions = {
        question.id: question.question
        for question in load_split("dev", data_dir / "raw" / "financebench")
    }
    pairs: list[Pair] = []
    for name in runs:
        answers = records(answers_root / name / "dev" / "answers.jsonl")
        drafts = records(answers_root / f"{name}-drafts" / "dev" / "answers.jsonl")
        pairs.extend(run_validator_pairs(answers, drafts, questions))
    return pairs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--from", dest="source", type=Path, help="a copy of the collections")
    parser.add_argument("--runs", nargs="*", default=[], help="local copilot runs' revisions")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--out", type=Path, help="default: data/processed/preferences")
    args = parser.parse_args(argv)

    settings = get_settings()
    out = args.out or settings.data_dir / "processed" / "preferences"
    if args.source is not None:
        documents = read_copy(args.source)
    else:
        documents = from_firestore(args.project)
        write_copy(documents, out / "firestore")
    feedback = [decoded(doc) for doc in documents["feedback"]]
    preferences = [decoded(doc) for doc in documents["preferences"]]

    pairs = [
        *retry_pairs(preferences),
        *rating_pairs(feedback),
        *exchange_validator_pairs(feedback),
        *run_pairs(args.runs, settings.data_dir),
    ]
    out.mkdir(parents=True, exist_ok=True)
    with (
        (out / "pairs.jsonl").open("w", encoding="utf-8", newline="\n") as trl,
        (out / "pairs-meta.jsonl").open("w", encoding="utf-8", newline="\n") as meta,
    ):
        for pair in pairs:
            trl.write(json.dumps(pair.trl(), ensure_ascii=False) + "\n")
            meta.write(json.dumps(pair.meta(), ensure_ascii=False) + "\n")

    held = sum(bool(rating.get("exchange")) for rating in feedback)
    print(f"{len(feedback)} ratings ({held} with their answer), {len(preferences)} picks")
    counts = Counter((pair.source, pair.prompt_kind) for pair in pairs)
    for (source, kind), count in sorted(counts.items()):
        print(f"  {source}: {count} pairs, prompt: {kind}")
    print(f"Wrote {len(pairs)} pairs to {out / 'pairs.jsonl'} and {out / 'pairs-meta.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
