"""Run FinanceBench questions through the copilot's graph, resumably (step 5.6).

Each question of the split (dev unless --split test) goes through the whole graph in batch
mode (`build_components(batch=True)`: paced calls, and a spent quota stops the run so it can
resume): rewrite, understand, route, the specialist, synthesise, validate (and revise),
respond and remember, on a thread of its own. A first question makes no rewrite call, and
batch runs keep no notes. Every event is appended to data/traces/<run>.jsonl, and each
answer to data/processed/answers/<run>/<split>/answers.jsonl in the doc agent's format, so
`poe judge-answers --run <run>` and `poe check-faithfulness --run <run>` score it like any
answer run. Each record also keeps what the copilot did:

- `route`, the router that decided and its model, and `steps`, the nodes it ran;
- `tool_ok`: the specialist answered or declined on purpose, rather than failing;
- `handoff`: set when the doc agent answered a question the data agent couldn't;
- `tokens_by_model` and `cost_usd` from the nodes' usage events, and `seconds`;
- `validation`, and `revisions`.

The specialist's answer before validation goes to
data/processed/answers/<run>-drafts/<split>/answers.jsonl, so judging both runs measures
what the validator changed on the same questions. When every question is done,
eval/results/copilot/<run>/<split>/ gets the agent metrics: steps per task, tool success,
cost and time per task, by route.

`--lenient` answers as the API does when a model's reply is unreadable: a check whose
reply the provider refuses as invalid JSON lets the answer pass unchecked, and the record's
`validation` says so. It is for a question whose check fails that way every time, which a
strict run can never finish; a spent quota still stops the run.

Usage (needs Qdrant, the facts database and GROQ_API_KEY):
  uv run poe run-copilot --run copilot-v1
  uv run poe run-copilot --run copilot-smoke --limit 2
  uv run poe run-copilot --run nightly-slice --ids eval/nightly/slice.json  # the nightly slice
  uv run poe run-copilot --run copilot-v2 --split test --allow-test   # milestone runs only
  uv run poe run-copilot --run copilot-v2 --ids stuck.json --lenient   # one stuck question
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig

from copilot.agents.build import build_components
from copilot.agents.runner import Copilot, TraceWriter
from copilot.answer.hybrid import database_source
from copilot.config import get_settings
from copilot.eval.financebench import Question
from copilot.eval.report import (
    RESULTS_DIR,
    RETRY_LATER,
    RunSummary,
    summarise,
    summarise_by,
    write_run,
)
from copilot.eval.splits import HeldOutError, load_split
from copilot.llm import LLMError
from copilot.llm.gateway import token_cost
from copilot.logs import configure_logging
from copilot.sql.tool import DataAnswer

METRICS = ["answered", "tool_ok", "handed_on", "revised", "steps", "cost_usd", "seconds"]


def read_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line cut short by a kill; that question runs again
        records[record["id"]] = record
    return records


def as_answer(question: Question, result: dict[str, Any]) -> dict[str, Any]:
    """A specialist's result in the shape the answer judges read."""
    kind = result.get("kind", "")
    base = {"id": question.id, "question_type": question.question_type, "kind": kind}
    if kind in ("doc", "hybrid") and "answer" in result:
        answer = result["answer"]
        return base | {
            "answerable": answer["answerable"],
            "text": answer["text"],
            "missing": answer["missing"],
            "error": answer["error"],
            "sources": answer["sources"],
            "cited": answer["cited"],
            "calculations": answer["calculations"],
        }
    if kind == "data" and "data" in result:
        data = DataAnswer.model_validate({"question": question.question, **result["data"]})
        source = database_source(data)
        return base | {
            "answerable": data.ok,
            "text": data.answer,
            "missing": "" if data.ok else data.answer,
            "error": data.answer if data.status == "error" else None,
            "sources": [vars_of(source)] if source else [],
            "cited": [],  # a data answer cites its query as a whole, not sentence by sentence
            "calculations": [],
        }
    # Small talk, a brief note or a decline: not an answer to a benchmark question.
    return base | {
        "answerable": False,
        "text": "",
        "missing": result.get("text", ""),
        "error": None,
        "sources": [],
        "cited": [],
        "calculations": [],
    }


def vars_of(source: Any) -> dict[str, Any]:
    return {
        "number": source.number,
        "doc_name": source.doc_name,
        "page": source.page,
        "label": source.label,
        "text": source.text,
        "tokens": source.tokens,
    }


def tool_ok(result: dict[str, Any]) -> bool:
    """The specialist answered, or declined on purpose, rather than failing."""
    kind = result.get("kind", "")
    if kind in ("doc", "hybrid"):
        data = result.get("data") or {}
        return result["answer"]["error"] is None and data.get("status") != "error"
    if kind == "data":
        return bool(result["data"]["status"] != "error")
    return True


def quota_hit(events: Sequence[dict[str, Any]], result: dict[str, Any]) -> bool:
    """A spent quota shaped the reply, which only a lenient run lets through: the API would
    ask the user to try again, or show a query's rows without their written analysis."""
    data = result.get("data") or {}
    return any(event.get("event") == "quota" for event in events) or bool(data.get("rate_limited"))


def draft_before_validation(copilot: Copilot, config: RunnableConfig) -> dict[str, Any]:
    """The specialist's result as it stood before its first check."""
    before: dict[str, Any] = {}
    for snapshot in copilot.graph.get_state_history(config):  # newest first
        if snapshot.next == ("validate",):
            before = snapshot.values.get("result", {})
    return before


def usage(events: Sequence[dict[str, Any]]) -> dict[str, list[int]]:
    total: dict[str, list[int]] = {}
    for event in events:
        if event["type"] == "event" and event.get("event") == "usage":
            for model, (prompt, completion) in event["tokens_by_model"].items():
                used = total.setdefault(model, [0, 0])
                used[0] += prompt
                used[1] += completion
    return total


def cost(tokens: dict[str, list[int]]) -> float | None:
    prices = [
        token_cost(model, prompt, completion) for model, (prompt, completion) in tokens.items()
    ]
    return round(sum(p for p in prices if p is not None), 7) if None not in prices else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="run name")
    parser.add_argument("--limit", type=int, help="only the first N questions of the split")
    parser.add_argument(
        "--ids", type=Path, help="only the questions a JSON file's `ids` list names"
    )
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="as the API: an unreadable reply lets the answer pass unchecked",
    )
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    try:
        questions = load_split(
            args.split, settings.data_dir / "raw" / "financebench", allow_test=args.allow_test
        )
    except HeldOutError:
        print("FinanceBench's test split is held out. Add --allow-test only for a milestone run.")
        return 2
    if args.ids is not None:
        wanted = set(json.loads(args.ids.read_text(encoding="utf-8"))["ids"])
        questions = [question for question in questions if question.id in wanted]
    questions = questions[: args.limit]
    answers_root = settings.data_dir / "processed" / "answers"
    out_path = answers_root / args.run / args.split / "answers.jsonl"
    drafts_path = answers_root / f"{args.run}-drafts" / args.split / "answers.jsonl"
    for path in (out_path, drafts_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    done = read_records(out_path)
    drafted = read_records(drafts_path)

    todo = [question for question in questions if question.id not in done]
    print(f"{len(questions)} questions, {len(done)} already answered, {len(todo)} to go")
    if todo:
        trace = TraceWriter(settings.data_dir / "traces" / f"{args.run}.jsonl")
        components = build_components(settings, batch=True)
        if args.lenient:
            components = replace(components, strict=False)
        copilot = Copilot(components, trace=trace)
        with (
            out_path.open("a", encoding="utf-8", newline="\n") as out,
            drafts_path.open("a", encoding="utf-8", newline="\n") as drafts,
        ):
            for number, question in enumerate(todo, start=1):
                thread = f"{args.run}-{question.id}"
                config: RunnableConfig = {"configurable": {"thread_id": thread}}
                started = time.perf_counter()
                try:
                    events = list(copilot.stream(question.question, thread_id=thread))
                except LLMError as exc:
                    reason = "a model's quota is used up" if exc.rate_limited else str(exc)[:200]
                    print(f"Stopped at {question.id}: {reason}. Run again later.")
                    return RETRY_LATER
                state = copilot.graph.get_state(config).values
                result = state.get("result", {})
                if quota_hit(events, result):
                    print(f"Stopped at {question.id}: a model's quota is used up. Run again later.")
                    return RETRY_LATER
                decision = state.get("decision", {})
                tokens = usage(events)
                record = as_answer(question, result) | {
                    "route": state.get("route", ""),
                    "router": decision.get("router"),
                    "router_model": decision.get("model"),
                    "router_error": decision.get("error"),
                    "path": result.get("path"),
                    "steps": [e["node"] for e in events if e["type"] == "start"],
                    "tool_ok": tool_ok(result),
                    "handoff": result.get("handoff"),
                    "validation": state.get("validation", {}),
                    "revisions": state.get("revisions", 0),
                    "similarity": result.get("similarity"),
                    "tokens_by_model": tokens,
                    "cost_usd": cost(tokens),
                    "seconds": round(time.perf_counter() - started, 2),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                done[question.id] = record
                if question.id not in drafted:
                    draft = as_answer(question, draft_before_validation(copilot, config))
                    drafts.write(json.dumps(draft, ensure_ascii=False) + "\n")
                    drafts.flush()
                print(
                    f"  {number}/{len(todo)} {question.id}: {record['route']} "
                    f"answered={record['answerable']} revisions={record['revisions']}"
                )

    rows = []
    for question in questions:
        record = done[question.id]
        rows.append(
            {
                "id": question.id,
                "question_type": question.question_type,
                "route": record["route"],
                "answered": float(record["answerable"]),
                "tool_ok": float(record["tool_ok"]),
                "handed_on": float(record.get("handoff") is not None),
                "revised": float(record["revisions"] > 0),
                "steps": float(len(record["steps"])),
                "cost_usd": record["cost_usd"] or 0.0,
                "seconds": record["seconds"],
            }
        )
    summary = RunSummary(
        suite="copilot",
        run=args.run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system={
            "graph": (
                "rewrite, understand, route, specialist (data on to doc when it finds nothing), "
                "synthesise, validate, respond, remember"
            ),
            "routes": dict(Counter(row["route"] for row in rows)),
            "router_fallbacks": sum(1 for q in questions if done[q.id].get("router_error")),
            "median_seconds": round(statistics.median(row["seconds"] for row in rows), 2),
        },
        metrics=summarise(rows, METRICS),
        by={
            "route": summarise_by(rows, METRICS, "route"),
            "question_type": summarise_by(rows, METRICS, "question_type"),
        },
    )
    results = args.results_dir / "copilot" / args.run / args.split
    write_run(results, summary, rows)
    print({name: round(value.mean, 4) for name, value in summary.metrics.items()})
    print(f"Wrote {results}, {out_path} and {drafts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
