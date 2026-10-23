"""Self-consistency on stored figure answers: sample more, vote, keep a new run (step 5.4).

Takes a doc-agent run's stored answers (data/processed/answers/<source>/dev/answers.jsonl)
for one question type, the figure questions by default. Each stored answer, written at
temperature 0, is the first vote; `--k` minus one more answers are sampled from the same
sources at temperature 0.7, each with its own seed, and `copilot.answer.consistency` keeps
the answer whose main figure most of them give. The kept answers go to
data/processed/answers/<run>/dev/answers.jsonl in the same shape, with a `consistency`
record (each vote's figure, the agreement, which answer was kept) and the samples'
tokens; a rerun skips the answers already there, and a spent quota stops the run.

Score the run and compare it with its source on the same questions:

  uv run poe self-consistency --source doc-agent-v4-full --k 3 --run doc-agent-v4-sc3
  uv run poe judge-answers --run doc-agent-v4-sc3
  uv run poe compare-runs eval/results/correctness/doc-agent-v4-full--qwen3.8-27b-p2/dev
      eval/results/correctness/doc-agent-v4-sc3--qwen3.8-27b-p2/dev --metric correct
      --where question_type=metrics-generated
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from copilot.agents.validator import to_answer
from copilot.answer.consistency import TEMPERATURE, key_figure, sample, vote
from copilot.answer.generate import Answer
from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.llm import LLMError, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging


def read_answers(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line cut short by a kill; that answer is sampled again
        records[record["id"]] = record
    return records


def updated(record: dict[str, Any], answer: Answer) -> dict[str, Any]:
    """The record with the kept answer in place of the stored one."""
    return record | {
        "answerable": answer.answerable,
        "text": answer.text,
        "missing": answer.missing,
        "cited": answer.cited,
        "invalid_citations": answer.invalid_citations,
        "calculations": [asdict(calculation) for calculation in answer.calculations],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source", required=True, help="the answers run to sample from")
    parser.add_argument("--run", required=True, help="the new run's name")
    parser.add_argument("--k", type=int, default=3, help="answers voting, the stored one included")
    parser.add_argument("--question-type", default="metrics-generated")
    args = parser.parse_args(argv)
    if args.k < 2:
        parser.error("--k must be at least 2")

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "processed" / "answers"
    source = read_answers(root / args.source / "dev" / "answers.jsonl")
    benchmark = {q.id: q for q in fb.load_questions(settings.data_dir / "raw" / "financebench")}
    chosen_ids = [
        answer_id
        for answer_id in source
        if answer_id in benchmark and benchmark[answer_id].question_type == args.question_type
    ]
    out_path = root / args.run / "dev" / "answers.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = read_answers(out_path)

    writer = PacedLLM(
        CachedLLM(
            LLMGateway(settings), settings.data_dir / "cache" / "llm.jsonl", role_models(settings)
        ),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    todo = [answer_id for answer_id in chosen_ids if answer_id not in done]
    print(f"{len(chosen_ids)} answers, {len(done)} already voted on, {len(todo)} to go")
    with out_path.open("a", encoding="utf-8", newline="\n") as out:
        for number, answer_id in enumerate(todo, start=1):
            record = source[answer_id]
            question = benchmark[answer_id].question
            greedy = to_answer(record, question)
            before = dict(writer.tokens_by_model)
            try:
                votes = [greedy] + [
                    sample(writer, question, greedy.sources, seed=seed) for seed in range(1, args.k)
                ]
            except LLMError as exc:
                reason = "the model's quota is used up" if exc.rate_limited else str(exc)[:200]
                print(f"Stopped at {answer_id}: {reason}. Run again later.")
                return 1
            kept, agreement = vote(votes)
            result = updated(record, votes[kept])
            result["consistency"] = {
                "k": args.k,
                "temperature": TEMPERATURE,
                "kept": kept,
                "agreement": round(agreement, 3),
                "figures": [
                    figure.text if (figure := key_figure(answer)) else None for answer in votes
                ],
                "answered": [answer.answerable for answer in votes],
            }
            result["consistency_tokens"] = {
                model: [
                    prompt - before.get(model, (0, 0))[0],
                    completion - before.get(model, (0, 0))[1],
                ]
                for model, (prompt, completion) in writer.tokens_by_model.items()
                if (prompt, completion) != before.get(model, (0, 0))
            }
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()
            print(
                f"  {number}/{len(todo)} {answer_id}: kept vote {kept} "
                f"(agreement {agreement:.2f}) figures={result['consistency']['figures']}"
            )
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
