"""Ask the copilot a question through its graph, with each step shown as it happens (step 5.1).

Each node's start and end, the route and the answer are printed as the graph streams them,
and every event is appended to data/traces/<thread>.jsonl. With `--thread`, questions join
one conversation, and a follow-up such as "And in 2019?" is rewritten from it; with
`--postgres`, the conversation and the notes kept about the user (`--user`) are stored in
the Compose Postgres and outlive the process, so a later `poe ask --thread NAME --postgres`
continues the conversation, and a new thread still knows the user's notes.

Usage (needs Qdrant, the facts database and GROQ_API_KEY):
  uv run poe ask "What was 3M's capital expenditure in 2018?"
  uv run poe ask "Hi! Which companies do you cover?" --thread demo --postgres
"""

from __future__ import annotations

import argparse
import contextlib
import json
import uuid
from collections.abc import Sequence
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from copilot.agents.build import build_components, postgres_checkpointer, postgres_store
from copilot.agents.runner import Copilot, TraceWriter
from copilot.config import get_settings
from copilot.llm import LLMError
from copilot.logs import configure_logging


def show(event: dict[str, Any], verbose: bool) -> None:
    kind = event["type"]
    if kind == "start" and verbose:
        print(f"  > {event['node']}")
    elif kind == "end":
        error = f"  error: {event['error']}" if event.get("error") else ""
        print(f"  < {event['node']:<11} {event['ms']:>8.0f} ms{error}")
    elif kind == "event" and event.get("event") == "route":
        reason = f": {event['reason']}" if event.get("reason") else ""
        print(f"    route {event['route']} ({event['router']}, {event.get('model')}){reason}")
    elif kind == "event" and event.get("event") == "usage" and verbose:
        print(f"    usage {json.dumps(event['tokens_by_model'])}, ${event['cost_usd']}")
    elif kind == "event" and verbose:
        rest = {k: v for k, v in event.items() if k not in ("ts", "run", "thread", "turn", "type")}
        print(f"    {json.dumps(rest, ensure_ascii=False, default=str)[:300]}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("question")
    parser.add_argument("--thread", help="conversation id (default: a new one)")
    parser.add_argument("--postgres", action="store_true", help="keep the conversation")
    parser.add_argument("--user", default="default", help="whose notes to use and keep")
    parser.add_argument("--verbose", action="store_true", help="print every event")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging("WARNING", settings.log_format)
    thread = args.thread or uuid.uuid4().hex[:8]
    trace = TraceWriter(settings.data_dir / "traces" / f"{thread}.jsonl")
    with contextlib.ExitStack() as stack:
        checkpointer: BaseCheckpointSaver[Any] | None = None
        store: BaseStore | None = None
        if args.postgres:
            checkpointer = stack.enter_context(postgres_checkpointer(settings))
            store = stack.enter_context(postgres_store(settings))
        copilot = Copilot(build_components(settings, store=store), checkpointer, trace)
        print(f"thread {thread}, turn {len(copilot.history(thread)) + 1}")
        response: dict[str, Any] = {}
        try:
            for event in copilot.stream(args.question, thread_id=thread, user_id=args.user):
                show(event, args.verbose)
                if event["type"] == "response":
                    response = event
        except LLMError as exc:
            print(f"Stopped: {exc}")
            return 1
    print()
    print(response.get("text", ""))
    if response.get("answered") and response.get("missing"):
        print()
        print(f"Not in the sources: {response['missing']}")
    for citation in response.get("citations", []):
        print(f"  [{citation['number']}] {citation['label']}")
    if response.get("sql"):
        print(f"\nSQL: {response['sql']}")
    print(f"\nTrace: {trace.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
