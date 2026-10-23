"""Judge a run's answers against FinanceBench's reference answers, resumably (step 3.6).

Reads data/processed/answers/<run>/dev/answers.jsonl and judges every answer in it that
hasn't been judged yet, appending each verdict to
data/processed/judgements/<run>/<judge>/judgements.jsonl as it arrives (the reasons can
quote the reference, so they stay local). Then writes ids and outcomes for every judged
answer to eval/results/correctness/<run>--<judge>/dev/:

- `correct`, `incorrect`, `refused`: FinanceBench's three outcomes, one of them 1 for each
  question. A refusal is never correct.

The run's answers file may still be growing; the summary says how many questions it covers.

The judge's name joins the model and the prompt version (qwen3.8-27b-p2), so verdicts
from different prompts never mix.

Usage: uv run poe judge-answers --run doc-agent-v3-full                 (the fast model)
       uv run poe judge-answers --run doc-agent-v3-full --role strong   (a second judge)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.judge import PROMPT_VERSION, ROLE, judge
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.splits import load_split
from copilot.llm import LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging

METRICS = ["correct", "incorrect", "refused"]


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """The records in a JSON Lines file by id; empty when the file doesn't exist."""
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def judge_name(model: str) -> str:
    """The judge's name in paths: the model and the prompt version, "qwen3.8-27b-p2"."""
    return f"{model.rsplit('/', 1)[-1]}-p{PROMPT_VERSION}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="the answers run to judge")
    parser.add_argument("--role", choices=["fast", "strong"], default=ROLE, help="judge model")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    role: ModelRole = args.role

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    answers = read_jsonl(
        settings.data_dir / "processed" / "answers" / args.run / "dev" / "answers.jsonl"
    )
    models = role_models(settings)
    name = judge_name(models[role])
    path = settings.data_dir / "processed" / "judgements" / args.run / name / "judgements.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = read_jsonl(path)

    # A cache file of its own, so a judge run never appends to the file an answer run uses.
    cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "judge.jsonl", models)
    llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    todo = [q for q in questions if q.id in answers and q.id not in done]
    print(f"{len(answers)} answers, {len(done)} already judged, {len(todo)} to go")
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            answer = answers[question.id]
            result = judge(
                llm,
                question.question,
                question.answer,
                answer["text"],
                justification=question.justification,
                answered=answer["answerable"],
                role=role,
            )
            item = {
                "id": question.id,
                "verdict": result.verdict,
                "reason": result.reason,
                "error": result.error,
                "model": result.model,
                "prompt_version": PROMPT_VERSION,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            }
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = item
            print(f"  {number}/{len(todo)} {question.id}: {result.verdict}")

    rows = [
        {
            "id": q.id,
            "question_type": q.question_type,
            **{metric: float(done[q.id]["verdict"] == metric) for metric in METRICS},
        }
        for q in questions
        if q.id in done
    ]
    judged = [done[q.id] for q in questions if q.id in done]
    summary = RunSummary(
        suite="correctness",
        run=f"{args.run}--{name}",
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "answers_run": args.run,
            "judge_model": models[role],
            "judge_prompt_version": PROMPT_VERSION,
            "judge_errors": sum(item["error"] is not None for item in judged),
            "judge_tokens": sum(
                item["prompt_tokens"] + item["completion_tokens"] for item in judged
            ),
            "verdicts": dict(Counter(item["verdict"] for item in judged)),
        },
        metrics=summarise(rows, METRICS),
        by={"question_type": summarise_by(rows, METRICS, "question_type")},
    )
    directory = args.results_dir / "correctness" / f"{args.run}--{name}" / "dev"
    write_run(directory, summary, rows)
    print({metric: round(value.mean, 3) for metric, value in summary.metrics.items()})
    print(f"Wrote {directory} and {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
