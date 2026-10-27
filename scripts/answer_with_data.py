"""Answer FinanceBench questions with the data agent, resumably (step 4.5).

The data agent (`copilot.sql.tool.DataAgent`) answers each dev question of the chosen
types with SQL over the facts database. Each answer is written as it arrives to
data/processed/answers/<run>/dev/answers.jsonl in the shape `poe judge-answers` reads (id,
answerable, text), with the whole typed answer beside it: the status, SQL, rows,
statistics, tables, attempts and tokens by model. The answers restate the questions'
figures, so the file stays local. A rerun skips questions already answered, and a run
stopped by a daily quota exits and carries on when run again.

The written answer comes from the strong model by default, the model that writes the doc
agent's answers, so the two agents differ only in where their numbers come from: SQL over
XBRL facts here, filing pages found by search there. `poe judge-answers` then grades both
the same way, and counts a decline or a failed query as a refusal.

Once every question has an answer, ids and numbers go to eval/results/answers/<run>/dev/:

- `answered`: the agent ran a query and answered from its rows;
- `declined`: it said the database can't answer the question;
- `failed`: no query worked after the repairs, or a model call failed;
- `repaired`: the first query failed and a repair ran;

with tokens, model latency and cost at list prices.

Usage: uv run poe answer-with-data                          (the dev metrics questions)
       uv run poe answer-with-data --limit 3 --run data-agent-smoke
       uv run poe answer-with-data --types all --run data-agent-all
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
from copilot.eval.financebench import Question
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.splits import load_split
from copilot.llm import ModelRole
from copilot.llm.gateway import token_cost
from copilot.logs import configure_logging
from copilot.sql.agent import batch_client
from copilot.sql.tool import DataAgent, DataAnswer

METRICS = ["answered", "declined", "failed", "repaired"]
TYPES = ("metrics-generated", "domain-relevant", "novel-generated")

Usage = dict[str, tuple[int, int]]  # model: (prompt tokens, completion tokens)


def read_answers(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def usage_since(before: Usage, after: Usage) -> dict[str, list[int]]:
    """Tokens by model between two snapshots of the client's counters."""
    used = {}
    for model, (prompt, completion) in after.items():
        old_prompt, old_completion = before.get(model, (0, 0))
        if (prompt, completion) != (old_prompt, old_completion):
            used[model] = [prompt - old_prompt, completion - old_completion]
    return used


def record(
    question: Question,
    answer: DataAnswer,
    tokens: dict[str, list[int]],
    latency_s: float,
    wall_s: float,
) -> dict[str, Any]:
    """Everything about one answer, for the local answers file."""
    return {
        "id": question.id,
        "question_type": question.question_type,
        "answerable": answer.ok,
        "text": answer.answer,
        "status": answer.status,
        "data": answer.model_dump(mode="json", exclude={"question"}),
        "tokens_by_model": tokens,
        "prompt_tokens": sum(prompt for prompt, _ in tokens.values()),
        "completion_tokens": sum(completion for _, completion in tokens.values()),
        "latency_s": round(latency_s, 3),
        "wall_s": round(wall_s, 3),
    }


def scores(item: dict[str, Any]) -> dict[str, Any]:
    """The automatic measures for one answer; no text."""
    data = item["data"]
    costs = [
        token_cost(model, prompt, completion)
        for model, (prompt, completion) in item["tokens_by_model"].items()
    ]
    known = [cost for cost in costs if cost is not None]
    return {
        "id": item["id"],
        "question_type": item["question_type"],
        "answered": float(item["status"] == "ok"),
        "declined": float(item["status"] == "unanswerable"),
        "failed": float(item["status"] == "error"),
        "repaired": float(data["attempts"] > 1),
        "attempts": data["attempts"],
        "rows": len(data["rows"]),
        "tables": len(data["tables"]),
        "prompt_tokens": item["prompt_tokens"],
        "completion_tokens": item["completion_tokens"],
        "latency_s": item["latency_s"],
        "cost_usd": round(sum(known), 6) if len(known) == len(costs) else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", default="data-agent-v1", help="run name")
    parser.add_argument(
        "--types",
        nargs="+",
        choices=[*TYPES, "all"],
        default=["metrics-generated"],
        help="the question types to answer",
    )
    parser.add_argument(
        "--analysis-model",
        choices=["fast", "strong"],
        default="strong",
        help="the model that writes the answer from the rows",
    )
    parser.add_argument("--limit", type=int, help="answer only the first N questions")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    analysis_model: ModelRole = args.analysis_model
    types = set(TYPES) if "all" in args.types else set(args.types)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    split = load_split("dev", settings.data_dir / "raw" / "financebench")
    questions = [q for q in split if q.question_type in types][: args.limit]
    path = settings.data_dir / "processed" / "answers" / args.run / "dev" / "answers.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = read_answers(path)

    client = batch_client(settings)
    agent = DataAgent.build(settings, client, analysis_model=analysis_model)
    todo = [q for q in questions if q.id not in done]
    print(f"{len(questions)} questions, {len(done)} already answered, {len(todo)} to go")
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            before, latency = dict(client.tokens_by_model), client.latency_s
            started = time.perf_counter()
            answer = agent.ask(question.question)
            if answer.rate_limited:
                print(f"Stopped at {question.id}: the model's quota is used up. Run again later.")
                return 1
            tokens = usage_since(before, client.tokens_by_model)
            elapsed = time.perf_counter() - started
            item = record(question, answer, tokens, client.latency_s - latency, elapsed)
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = item
            print(f"  {number}/{len(todo)} {question.id}: {answer.status}")

    rows = [scores(done[q.id]) for q in questions]
    latencies = sorted(row["latency_s"] for row in rows)
    costs = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    models = {"fast": settings.llm_fast_model, "strong": settings.llm_strong_model}
    summary = RunSummary(
        suite="answers",
        run=args.run,
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "agent": "the data agent: text2sql-analyst over the facts database, value linking",
            "text2sql_analyst": text2sql.__version__,
            "question_types": sorted(types),
            "selection_model": models["fast"],
            "sql_model": models["strong"],
            "analysis_model": models[analysis_model],
            "mean_prompt_tokens": round(statistics.mean(row["prompt_tokens"] for row in rows)),
            "mean_completion_tokens": round(
                statistics.mean(row["completion_tokens"] for row in rows)
            ),
            "model_latency_s": {
                "p50": round(statistics.median(latencies), 2),
                "p95": round(latencies[int(0.95 * (len(latencies) - 1))], 2),
            },
            "cost_usd": {
                "total": round(sum(costs), 4),
                "per_question": round(statistics.mean(costs), 6) if costs else None,
                "priced_questions": len(costs),
            },
            "limit": args.limit,
        },
        metrics=summarise(rows, METRICS),
        by={"question_type": summarise_by(rows, METRICS, "question_type")},
    )
    directory = args.results_dir / "answers" / args.run / "dev"
    write_run(directory, summary, rows)
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(f"Wrote {directory} and {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
