"""Answer the SQL set with the data agent and score it, resumably (Phase 4).

For each question of the split, the data agent (text2sql-analyst over the facts database,
`copilot.sql.agent`) writes SQL or declines. Each response is appended as it arrives to
eval/results/sql/<run>/<split>/trace.jsonl with how the agent got there: its status, the
tables it used, its SQL attempts, tokens and model time. A rerun skips questions already
answered, so a run stopped by a daily quota carries on the next day.

Once every question has a response, the responses are scored as `poe eval-sql` scores
them (execution accuracy; declining is right only for questions the database can't
answer) and written next to the trace, with predictions.jsonl for `poe eval-sql`. A
response that failed without any SQL counts as wrong, never as declining.

Usage: uv run poe run-sql-agent                              (dev, run sql-agent-v1)
       uv run poe run-sql-agent --run sql-agent-v2 --limit 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import text2sql

from copilot.config import get_settings
from copilot.eval import sql
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.splits import HeldOutError
from copilot.facts.database import connect_read_only
from copilot.logs import configure_logging
from copilot.sql.agent import batch_client, build_pipeline, facts_db_path

METRICS = ["accuracy"]


def read_trace(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def prediction(record: dict[str, Any]) -> sql.Prediction:
    """What the scorer sees: the SQL, or a decline; an error with no SQL is neither."""
    if record["status"] == "unanswerable":
        return sql.Prediction(id=record["id"], declined=True)
    return sql.Prediction(id=record["id"], sql=record["sql"] or "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", default="sql-agent-v1", help="run name")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--allow-test", action="store_true", help="open the held-out test split")
    parser.add_argument("--limit", type=int, help="answer only the first N questions")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    try:
        questions = sql.load_questions(args.split, allow_test=args.allow_test)[: args.limit]
    except HeldOutError:
        print("The SQL test split is held out. Add --allow-test only for a milestone run.")
        return 2
    directory = args.results_dir / "sql" / args.run / args.split
    directory.mkdir(parents=True, exist_ok=True)
    trace_path = directory / "trace.jsonl"
    done = read_trace(trace_path)

    client = batch_client(settings)
    pipeline = build_pipeline(settings, client)
    todo = [q for q in questions if q.id not in done]
    print(f"{len(questions)} questions, {len(done)} already answered, {len(todo)} to go")
    with trace_path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            before = (client.prompt_tokens, client.completion_tokens, client.latency_s)
            started = time.perf_counter()
            result = pipeline.ask(question.question, analyze=False)
            if result.rate_limited:
                print(f"Stopped at {question.id}: the model's quota is used up. Run again later.")
                return 1
            record: dict[str, Any] = {
                "id": question.id,
                "status": result.status,
                "sql": result.sql,
                "message": result.message,
                "tables": result.tables_used,
                "attempts": len(result.attempts),
                "errors": [a.error for a in result.attempts if a.error],
                "prompt_tokens": client.prompt_tokens - before[0],
                "completion_tokens": client.completion_tokens - before[1],
                "model_latency_s": round(client.latency_s - before[2], 3),
                "wall_s": round(time.perf_counter() - started, 3),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = record
            print(f"  {number}/{len(todo)} {question.id}: {result.status}")

    traces = [done[q.id] for q in questions]
    predictions = {record["id"]: prediction(record) for record in traces}
    (directory / "predictions.jsonl").write_text(
        "".join(p.model_dump_json(exclude_defaults=True) + "\n" for p in predictions.values()),
        encoding="utf-8",
        newline="\n",
    )
    conn = connect_read_only(facts_db_path(settings))
    try:
        rows = sql.score(questions, predictions, conn)
    finally:
        conn.close()
    for row, record in zip(rows, traces, strict=True):
        row |= {
            "status": record["status"],
            "attempts": record["attempts"],
            "tables": len(record["tables"]),
            "prompt_tokens": record["prompt_tokens"],
            "completion_tokens": record["completion_tokens"],
            "model_latency_s": record["model_latency_s"],
        }
    latencies = sorted(row["model_latency_s"] for row in rows)
    summary = RunSummary(
        suite="sql",
        run=args.run,
        split=args.split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=args.split == "test",
        system={
            "agent": "text2sql-analyst over the facts database, every table offered",
            "text2sql_analyst": text2sql.__version__,
            "sql_model": settings.llm_strong_model,
            "helper_model": settings.llm_fast_model,
            "repaired": sum(row["attempts"] > 1 for row in rows),
            "errors": sum(row["status"] == "error" for row in rows),
            "mean_tokens": round(
                statistics.mean(row["prompt_tokens"] + row["completion_tokens"] for row in rows)
            ),
            "model_latency_s": {
                "p50": round(statistics.median(latencies), 2),
                "p95": round(latencies[int(0.95 * (len(latencies) - 1))], 2),
            },
            "limit": args.limit,
        },
        metrics=summarise(rows, METRICS),
        by={
            "answerable": summarise_by(rows, METRICS, "answerable"),
            "difficulty": summarise_by(rows, METRICS, "difficulty"),
            "category": summarise_by(rows, METRICS, "category"),
        },
    )
    write_run(directory, summary, rows)
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
