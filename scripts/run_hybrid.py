"""Answer the hybrid questions, then check their figures and citations, resumably (step 4.6).

`--agent hybrid` answers each question in eval/hybrid/questions.jsonl with the hybrid agent
(`copilot.answer.hybrid`): the data agent's query result and the doc agent's pages in one
cited answer. `--agent doc` answers them with the doc agent alone, for comparison. Each
answer is appended as it arrives to data/processed/hybrid/<run>/answers.jsonl, with its
sources, and a rerun skips the questions already there. Then each answer's sentences are
checked against the sources they cite (`copilot.eval.faithfulness`, the Qwen judge, with its
own cache file), resumably too. A run stopped by a quota or an outage exits; run it again.

eval/results/hybrid/<run>/dev/ then gets, for each question:

- `answered`; `figures_given`, the share of the expected figures the answer gives
  (`copilot.eval.hybrid`), and `all_figures`;
- `database_cited` and `pages_cited`: whether it cites the query result, and a page;
- `faithful`: every sentence supported by the sources it cites; `supported`, the share of
  sentences that are (a refusal scores 0 on both);
- tokens, model time and cost at list prices;

and answers.jsonl with each answer's text, the labels of the sources it cites and, for the
hybrid agent, the SQL and rows. Filing text stays in the local file.

Usage: uv run poe run-hybrid --agent hybrid --run hybrid-v1     (needs Qdrant and GROQ_API_KEY)
       uv run poe run-hybrid --agent hybrid --run hybrid-smoke --limit 2
       uv run poe run-hybrid --agent doc --run doc-agent-v4
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.answer.agent import build_agent
from copilot.answer.generate import Answer
from copilot.answer.hybrid import DATABASE, HybridAgent
from copilot.config import get_settings
from copilot.eval.faithfulness import PROMPT_VERSION, check
from copilot.eval.hybrid import HybridQuestion, expected_values, gives, load_questions
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, write_run
from copilot.facts.database import connect_read_only
from copilot.llm import LLMError, LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import token_cost
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging
from copilot.sql.agent import batch_client, build_pipeline, facts_db_path
from copilot.sql.tool import DataAgent

METRICS = [
    "answered",
    "figures_given",
    "all_figures",
    "database_cited",
    "pages_cited",
    "faithful",
    "supported",
]
Usage = dict[str, tuple[int, int]]


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def usage(clients: Sequence[PacedLLM]) -> Usage:
    """Tokens by model across the clients, so far."""
    total: dict[str, tuple[int, int]] = {}
    for client in clients:
        for model, (prompt, completion) in client.tokens_by_model.items():
            old_prompt, old_completion = total.get(model, (0, 0))
            total[model] = (old_prompt + prompt, old_completion + completion)
    return total


def used(before: Usage, after: Usage) -> dict[str, list[int]]:
    spent = {}
    for model, (prompt, completion) in after.items():
        old_prompt, old_completion = before.get(model, (0, 0))
        if (prompt, completion) != (old_prompt, old_completion):
            spent[model] = [prompt - old_prompt, completion - old_completion]
    return spent


def record(
    question: HybridQuestion, agent: str, answer: Answer, extra: dict[str, Any]
) -> dict[str, Any]:
    """Everything about one answer, for the local answers file."""
    return {
        "id": question.id,
        "agent": agent,
        "answerable": answer.answerable,
        "text": answer.text,
        "missing": answer.missing,
        "error": answer.error,
        "sources": [asdict(source) for source in answer.sources],
        "cited": answer.cited,
        "invalid_citations": answer.invalid_citations,
        "calculations": [asdict(calculation) for calculation in answer.calculations],
        **extra,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--agent", choices=["hybrid", "doc"], required=True)
    parser.add_argument("--run", required=True, help="run name")
    parser.add_argument("--limit", type=int, help="answer only the first N questions")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    questions = load_questions()[: args.limit]
    directory = settings.data_dir / "processed" / "hybrid" / args.run
    directory.mkdir(parents=True, exist_ok=True)
    answers_path = directory / "answers.jsonl"
    done = read_jsonl(answers_path)

    doc = build_agent(settings)
    sql_client = batch_client(settings)
    hybrid = HybridAgent(doc, DataAgent(build_pipeline(settings, sql_client)))
    if not isinstance(doc.llm, PacedLLM):
        raise TypeError("the doc agent's client should be paced")
    clients = [doc.llm, sql_client]
    todo = [q for q in questions if q.id not in done]
    print(f"{len(questions)} questions, {len(done)} already answered, {len(todo)} to go")
    with answers_path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            before = usage(clients)
            latency = sum(client.latency_s for client in clients)
            try:
                if args.agent == "hybrid":
                    result = hybrid.answer(question.question)
                    answer, retrieval = result.answer, result.retrieval
                    extra: dict[str, Any] = {
                        "data": result.data.model_dump(mode="json", exclude={"question"})
                    }
                else:
                    agent_answer = doc.answer(question.question)
                    answer, retrieval = agent_answer.answer, agent_answer.retrieval
                    extra = {"retried": agent_answer.retried}
            except LLMError as exc:
                reason = "the model's quota is used up" if exc.rate_limited else str(exc)[:200]
                print(f"Stopped at {question.id}: {reason}. Run again later.")
                return 1
            extra |= {
                "filings": retrieval.filings,
                "tokens_by_model": used(before, usage(clients)),
                "latency_s": round(sum(client.latency_s for client in clients) - latency, 3),
            }
            item = record(question, args.agent, answer, extra)
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = item
            print(f"  {number}/{len(todo)} {question.id}: answered={answer.answerable}")

    # The faithfulness judge, with a cache file of its own, as `poe check-faithfulness` has.
    models: dict[ModelRole, str] = {
        "fast": settings.llm_fast_model,
        "strong": settings.llm_strong_model,
    }
    judge = PacedLLM(
        CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "faithfulness.jsonl", models),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    checks_path = directory / "faithfulness.jsonl"
    checks = read_jsonl(checks_path)
    with checks_path.open("a", encoding="utf-8", newline="\n") as out:
        for question in questions:
            item = done[question.id]
            if question.id in checks or not item["answerable"]:
                continue
            sources = {s["number"]: (s["label"], s["text"]) for s in item["sources"]}
            calculations = [(c["id"], c["expression"], c["value"]) for c in item["calculations"]]
            try:
                verdict = check(judge, item["text"], sources, calculations)
            except LLMError as exc:
                reason = "the judge's quota is used up" if exc.rate_limited else str(exc)[:200]
                print(f"Stopped checking {question.id}: {reason}. Run again later.")
                return 1
            entry = {
                "id": question.id,
                "faithful": verdict.faithful,
                "supported": verdict.supported_sentences,
                "sentences": len(verdict.checks),
                "checks": [asdict(c) for c in verdict.checks],
                "error": verdict.error,
                "prompt_version": PROMPT_VERSION,
            }
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out.flush()
            checks[question.id] = entry
            print(f"  checked {question.id}: {verdict.supported_sentences}/{len(verdict.checks)}")

    conn = connect_read_only(facts_db_path(settings))
    try:
        expected = {q.id: expected_values(q, conn) for q in questions}
    finally:
        conn.close()
    rows, published = [], []
    for question in questions:
        item = done[question.id]
        text = item["text"] if item["answerable"] else ""
        given = [gives(text, accepted) for accepted in expected[question.id]]
        cited = [s for s in item["sources"] if s["number"] in item["cited"]]
        checked = checks.get(question.id)
        costs = [token_cost(m, p, c) for m, (p, c) in item["tokens_by_model"].items()]
        known = [cost for cost in costs if cost is not None]
        rows.append(
            {
                "id": question.id,
                "agent": args.agent,
                "answered": float(item["answerable"]),
                "figures_given": sum(given) / len(given),
                "all_figures": float(all(given)),
                "database_cited": float(any(s["doc_name"] == DATABASE for s in cited)),
                "pages_cited": float(any(s["doc_name"] != DATABASE for s in cited)),
                "faithful": float(bool(checked and checked["faithful"])),
                "supported": checked["supported"] / checked["sentences"]
                if checked and checked["sentences"]
                else 0.0,
                "prompt_tokens": sum(p for p, _ in item["tokens_by_model"].values()),
                "completion_tokens": sum(c for _, c in item["tokens_by_model"].values()),
                "latency_s": item["latency_s"],
                "cost_usd": round(sum(known), 6) if len(known) == len(costs) else None,
            }
        )
        data = item.get("data") or {}
        published.append(
            {
                "id": question.id,
                "agent": args.agent,
                "answerable": item["answerable"],
                "text": item["text"],
                "missing": item["missing"],
                "cited": [s["label"] for s in cited],
                "data_status": data.get("status"),
                "sql": data.get("sql"),
                "rows": data.get("rows"),
            }
        )

    latencies = sorted(row["latency_s"] for row in rows)
    priced = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    summary = RunSummary(
        suite="hybrid",
        run=args.run,
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "agent": args.agent,
            "questions": f"eval/hybrid/questions.jsonl, {len(questions)} on dev companies",
            "answer_model": settings.llm_strong_model,
            "faithfulness_judge": f"{settings.llm_fast_model}, prompt {PROMPT_VERSION}",
            "mean_tokens": round(
                statistics.mean(row["prompt_tokens"] + row["completion_tokens"] for row in rows)
            ),
            "model_latency_s": {
                "p50": round(statistics.median(latencies), 2),
                "max": round(latencies[-1], 2),
            },
            "cost_usd_per_question": round(statistics.mean(priced), 6) if priced else None,
        },
        metrics=summarise(rows, METRICS),
    )
    results = args.results_dir / "hybrid" / args.run / "dev"
    write_run(results, summary, rows)
    with (results / "answers.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for entry in published:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print({name: round(value.mean, 3) for name, value in summary.metrics.items()})
    print(f"Wrote {results} and {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
