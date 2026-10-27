"""Answer FinanceBench's dev questions with one answer arm, from a run's sources (step 7.5).

The arms (`copilot.answer.bandit.ARMS`) differ only in the model setting that writes the
answer. To compare them on the same evidence, each arm answers every question from the
sources the doc agent's final answer was written from in the source run (by default
`doc-agent-v4-cerebras`): its first context, or its second when it retried. One call a
question, no search. The records go to data/processed/answers/<run>/dev/answers.jsonl in the
doc agent's own format, so `poe judge-answers --run <run>` grades them the same way.

New calls go to data/cache/arms.jsonl, and the source run's calls replay from llm.jsonl, so
the `strong` arm reproduces the source run's final answers at no cost.

Usage (the roles on Cerebras, as the source run):
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \\
  FRC_LLM_TOKENS_PER_MINUTE=100000 uv run poe run-answer-arm --arm strong-low --run arm-strong-low
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from copilot.answer.bandit import ARMS
from copilot.answer.context import Source
from copilot.answer.generate import PROMPT_VERSION, generate
from copilot.config import get_settings
from copilot.eval.splits import load_split
from copilot.llm import LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {record["id"]: record for record in records}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--run", required=True, help="the run name for the arm's answers")
    parser.add_argument("--source", default="doc-agent-v4-cerebras", help="whose sources")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    arm = ARMS[args.arm]
    answers = settings.data_dir / "processed" / "answers"
    source = read_jsonl(answers / args.source / "dev" / "answers.jsonl")
    path = answers / args.run / "dev" / "answers.jsonl"
    done = read_jsonl(path)
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    todo = [q for q in questions if q.id in source and q.id not in done]
    print(f"{len(source)} source answers, {len(done)} already answered, {len(todo)} to go")

    models = role_models(settings)
    caches = settings.data_dir / "cache"
    cache = CachedLLM(
        LLMGateway(settings), caches / "arms.jsonl", models, also_read=[caches / "llm.jsonl"]
    )
    llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            base = source[question.id]
            sources = [Source(**record) for record in base["sources"]]
            answer = generate(llm, question.question, sources, role=arm.role, **arm.settings)
            item = {
                "id": question.id,
                "question_type": question.question_type,
                "answerable": answer.answerable,
                "text": answer.text,
                "missing": answer.missing,
                "error": answer.error,
                "sources": [asdict(s) for s in answer.sources],
                "cited": answer.cited,
                "invalid_citations": answer.invalid_citations,
                "calculations": [asdict(c) for c in answer.calculations],
                "filings": base["filings"],
                "searches": base["searches"],
                "retried": False,
                "first_missing": None,
                "model": answer.model,
                "prompt_version": PROMPT_VERSION,
                "prompt_tokens": answer.prompt_tokens,
                "completion_tokens": answer.completion_tokens,
                "latency_s": round(answer.latency_s, 3),
                "arm": arm.name,
                "arm_settings": arm.settings,
                "source_run": args.source,
            }
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  {number}/{len(todo)} {question.id}: answered={answer.answerable}")
    print(f"cache: {cache.hits} hits, {cache.misses} misses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
