"""Run the validator over a run's stored answers and keep the result as a new run (step 5.3).

Reads the answers a doc-agent run left in data/processed/answers/<source>/dev/answers.jsonl.
Each answered one is checked by the validator (`copilot.agents.validator`: gpt-oss-20b on
the small role); a failing answer is written again by the answer model at most twice, and
what still fails after that is trimmed to its verified sentences, or declined. Every answer,
changed or not, goes to data/processed/answers/<run>/dev/answers.jsonl in the same shape,
with a `validation` record and the validator's own tokens, as it is done; a rerun skips the
answers already there, and a spent quota stops the run so it can resume.

The checks are cached in data/cache/validator.jsonl and the revisions in
data/cache/llm.jsonl. The new run is then scored like any doc-agent run:

  uv run poe validate-answers --source doc-agent-v4-full --run doc-agent-v4-validated
  uv run poe check-faithfulness --run doc-agent-v4-validated
  uv run poe judge-answers --run doc-agent-v4-validated
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from copilot.agents.validator import (
    MAX_REVISIONS,
    PROMPT_VERSION,
    check_answer,
    failing,
    revise,
    to_answer,
    trim,
)
from copilot.answer.generate import SYSTEM_PROMPT, Answer
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
            continue  # a line cut short by a kill; the answer is validated again
        records[record["id"]] = record
    return records


def updated(record: dict[str, Any], answer: Answer) -> dict[str, Any]:
    """The record with the validated answer in place of the stored one."""
    return record | {
        "answerable": answer.answerable,
        "text": answer.text,
        "missing": answer.missing,
        "cited": answer.cited,
        "invalid_citations": answer.invalid_citations,
        "calculations": [asdict(calculation) for calculation in answer.calculations],
    }


def validate(
    record: dict[str, Any], question: str, checker: PacedLLM, writer: PacedLLM
) -> dict[str, Any]:
    """One stored answer through the validator: check, revise at most twice, trim."""
    answer = to_answer(record, question)
    verdict = check_answer(checker, answer)
    first = verdict.faithful
    revisions = 0
    while not verdict.faithful and revisions < MAX_REVISIONS and answer.answerable:
        answer = revise(writer, SYSTEM_PROMPT, question, answer, failing(verdict))
        revisions += 1
        if answer.answerable:
            verdict = check_answer(checker, answer)
    dropped: list[str] = []
    if answer.answerable and not verdict.faithful:
        answer, dropped = trim(answer, verdict)
    result = updated(record, answer)
    result["validation"] = {
        "prompt_version": PROMPT_VERSION,
        "checked": True,
        "faithful_first": first,
        "revisions": revisions,
        "faithful": answer.answerable and verdict.faithful,
        "trimmed": bool(dropped),
        "unverified": dropped,
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source", required=True, help="the answers run to validate")
    parser.add_argument("--run", required=True, help="the new run's name")
    parser.add_argument("--limit", type=int, help="validate only the first N answers")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "processed" / "answers"
    source = read_answers(root / args.source / "dev" / "answers.jsonl")
    if not source:
        print(f"No answers for {args.source}.")
        return 2
    benchmark = fb.load_questions(settings.data_dir / "raw" / "financebench")
    questions = {question.id: question.question for question in benchmark}
    out_path = root / args.run / "dev" / "answers.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = read_answers(out_path)

    models = role_models(settings)
    cache_dir = settings.data_dir / "cache"
    checker = PacedLLM(
        CachedLLM(LLMGateway(settings), cache_dir / "validator.jsonl", models),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    writer = PacedLLM(
        CachedLLM(LLMGateway(settings), cache_dir / "llm.jsonl", models),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    ids = list(source)[: args.limit]
    todo = [answer_id for answer_id in ids if answer_id not in done]
    print(f"{len(ids)} answers, {len(done)} already validated, {len(todo)} to go")
    with out_path.open("a", encoding="utf-8", newline="\n") as out:
        for number, answer_id in enumerate(todo, start=1):
            record = source[answer_id]
            if not record["answerable"]:
                result = record | {"validation": {"checked": False}}
            else:
                before_checker = dict(checker.tokens_by_model)
                before_writer = dict(writer.tokens_by_model)
                try:
                    result = validate(record, questions[answer_id], checker, writer)
                except LLMError as exc:
                    reason = "the model's quota is used up" if exc.rate_limited else str(exc)[:200]
                    print(f"Stopped at {answer_id}: {reason}. Run again later.")
                    return 1
                result["validation_tokens"] = spent(
                    [(before_checker, checker), (before_writer, writer)]
                )
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()
            validation = result["validation"]
            print(
                f"  {number}/{len(todo)} {answer_id}: checked={validation['checked']} "
                f"revisions={validation.get('revisions', 0)} "
                f"faithful={validation.get('faithful')}"
            )
    print(f"Wrote {out_path}")
    return 0


def spent(pairs: Sequence[tuple[dict[str, tuple[int, int]], PacedLLM]]) -> dict[str, list[int]]:
    """Tokens by model that the clients used since their counts in each pair were taken."""
    total: dict[str, list[int]] = {}
    for before, client in pairs:
        for model, (prompt, completion) in client.tokens_by_model.items():
            old_prompt, old_completion = before.get(model, (0, 0))
            if (prompt, completion) != (old_prompt, old_completion):
                used = total.setdefault(model, [0, 0])
                used[0] += prompt - old_prompt
                used[1] += completion - old_completion
    return total


if __name__ == "__main__":
    raise SystemExit(main())
