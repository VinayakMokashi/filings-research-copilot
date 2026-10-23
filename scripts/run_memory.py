"""Run the memory set: follow-up rewriting and notes, conversation by conversation (step 5.5).

eval/memory/conversations.jsonl holds conversations written for this project, one or two
per user, and each turn names the companies, years and terms its standalone question must
carry. Every turn goes through `copilot.agents.memory` as the graph's rewrite and remember
nodes use it, with a written reply standing in for the specialists:

1. the rewrite (strong role) sees the conversation's earlier turns and the user's notes;
2. then the notes (small role) are updated from the turn.

One store serves the whole run, so a user's second conversation starts with the notes the
first one left. Calls are cached in data/cache/rewrite.jsonl and data/cache/notes.jsonl
and paced; a stopped run starts again from the first turn and replays what it paid for.

eval/results/memory/<run>/dev/ gets a row per turn: the rewrite, `resolved` (it names
exactly the expected companies, the years and the terms) and, for questions that already
stood alone, `unchanged`. notes.json holds each user's final notes, checked against
eval/memory/notes.jsonl: the terms they should mention, and those they shouldn't.

Usage: uv run poe run-memory --run memory-v1      (needs GROQ_API_KEY)
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.store.memory import InMemoryStore

from copilot.agents.memory import (
    PROMPT_VERSION,
    apply,
    extract,
    recall,
    reconcile,
    rewrite_followup,
)
from copilot.config import get_settings
from copilot.eval.financebench import read_jsonl
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.ingest.universe import read_companies
from copilot.llm import LLMError, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging
from copilot.retrieval.query import CompanyMatcher, understand

# Found beside this script, so it can run from another checkout that holds the data.
SET_DIR = Path(__file__).resolve().parents[1] / "eval" / "memory"
CONVERSATIONS = SET_DIR / "conversations.jsonl"
NOTES = SET_DIR / "notes.jsonl"
METRICS = ["resolved", "rewritten"]


def check(standalone: str, turn: dict[str, Any], matcher: CompanyMatcher) -> bool:
    """The rewrite names exactly the expected companies, and the years and terms."""
    cues = understand(standalone, matcher)
    lower = standalone.lower()
    return (
        set(cues.companies) == set(turn["companies"])
        and set(turn["years"]) <= set(cues.years)
        and all(term.lower() in lower for term in turn["terms"])
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="run name")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    conversations = read_jsonl(CONVERSATIONS)
    expected_notes = {record["user"]: record for record in read_jsonl(NOTES)}
    companies = read_companies()
    matcher = CompanyMatcher(
        [company.name for company in companies],
        {company.name: company.ticker for company in companies},
    )
    models = role_models(settings)

    def client(cache_file: str) -> PacedLLM:
        cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / cache_file, models)
        return PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)

    rewriter, noter = client("rewrite.jsonl"), client("notes.jsonl")
    store = InMemoryStore()
    rows: list[dict[str, Any]] = []
    for conversation in conversations:
        user = conversation["user"]
        turns: list[tuple[str, str]] = []
        for number, turn in enumerate(conversation["turns"], start=1):
            notes = [note.text for note in recall(store, user)]
            try:
                result = rewrite_followup(rewriter, turns, turn["question"], notes)
                facts = extract(noter, turn["question"], turn["answer"])
                done = apply(store, user, reconcile(noter, recall(store, user), facts))
            except LLMError as exc:
                reason = "a model's quota is used up" if exc.rate_limited else str(exc)[:200]
                print(f"Stopped at {conversation['id']} turn {number}: {reason}. Run again later.")
                return 1
            turns.append((result.standalone, turn["answer"]))
            row = {
                "id": f"{conversation['id']}-{number}",
                "user": user,
                "kind": turn["kind"],
                "question": turn["question"],
                "standalone": result.standalone,
                "rewritten": float(result.rewritten),
                "resolved": float(check(result.standalone, turn, matcher)),
                "notes_before": len(notes),
                "facts": facts,
                "operations": done,
                "error": result.error,
            }
            if turn["kind"] == "standalone":
                row["unchanged"] = float(result.standalone == turn["question"])
            rows.append(row)
            print(
                f"  {row['id']} {turn['kind']}: resolved={row['resolved']} -> {result.standalone}"
            )

    users = sorted({conversation["user"] for conversation in conversations})
    final: dict[str, Any] = {}
    for user in users:
        texts = [note.text for note in recall(store, user)]
        joined = " ".join(texts).lower()
        expected = expected_notes.get(user, {"present": [], "absent": []})
        final[user] = {
            "notes": texts,
            "present": {term: term.lower() in joined for term in expected["present"]},
            "absent": {term: term.lower() not in joined for term in expected["absent"]},
        }
    checks = [
        ok
        for user in final.values()
        for ok in [*user["present"].values(), *user["absent"].values()]
    ]

    usage = {**rewriter.tokens_by_model}
    for model, (prompt, completion) in noter.tokens_by_model.items():
        old_prompt, old_completion = usage.get(model, (0, 0))
        usage[model] = (old_prompt + prompt, old_completion + completion)
    standalone_rows = [row for row in rows if "unchanged" in row]
    summary = RunSummary(
        suite="memory",
        run=args.run,
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "set": f"eval/memory, {len(conversations)} conversations, {len(users)} users",
            "rewrite_model": models["strong"],
            "notes_model": models["small"],
            "prompt_version": PROMPT_VERSION,
            "unchanged_when_standalone": sum(r["unchanged"] for r in standalone_rows),
            "standalone_turns": len(standalone_rows),
            "note_checks_passed": f"{sum(checks)} of {len(checks)}",
            "tokens_by_model": {model: list(tokens) for model, tokens in usage.items()},
        },
        metrics=summarise(rows, METRICS),
        by={"kind": summarise_by(rows, METRICS, "kind")},
    )
    results = args.results_dir / "memory" / args.run / "dev"
    write_run(results, summary, rows)
    (results / "notes.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(f"Notes checks: {sum(checks)} of {len(checks)} pass. Wrote {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
