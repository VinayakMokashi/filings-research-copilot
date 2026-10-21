"""Check whether each answer's sentences are supported by the sources they cite (step 3.7).

Reads data/processed/answers/<run>/dev/answers.jsonl and checks every answered question
not checked yet, appending the sentence verdicts to
data/processed/faithfulness/<run>/<judge>/checks.jsonl as they arrive (they quote the
answers, so they stay local). Then writes measures for every checked answer, by id, to
eval/results/faithfulness/<run>--<judge>/dev/:

- `faithful`: every sentence cites a source and is supported by what it cites;
- `supported_share`: the share of an answer's sentences that are supported (a sentence
  that cites nothing counts as unsupported);
- citation precision over all citations of the run, in the summary.

Usage: uv run poe check-faithfulness --run doc-agent-v3-full
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.faithfulness import PROMPT_VERSION, ROLE, check
from copilot.eval.report import RESULTS_DIR, RunSummary, summarise, summarise_by, write_run
from copilot.eval.splits import load_split
from copilot.llm import LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging

METRICS = ["faithful", "supported_share"]


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines if line.strip())
    return {record["id"]: record for record in records}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="the answers run to check")
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
    models: dict[ModelRole, str] = {
        "fast": settings.llm_fast_model,
        "strong": settings.llm_strong_model,
    }
    name = f"{models[role].rsplit('/', 1)[-1]}-f{PROMPT_VERSION}"
    path = settings.data_dir / "processed" / "faithfulness" / args.run / name / "checks.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = read_jsonl(path)

    # A cache file of its own, so this never appends to a file another run is writing.
    cache = CachedLLM(
        LLMGateway(settings), settings.data_dir / "cache" / "faithfulness.jsonl", models
    )
    llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    todo = [q for q in questions if answers.get(q.id, {}).get("answerable") and q.id not in done]
    print(f"{len(answers)} answers, {len(done)} already checked, {len(todo)} to go")
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, question in enumerate(todo, start=1):
            answer = answers[question.id]
            sources = {s["number"]: (s["label"], s["text"]) for s in answer["sources"]}
            calculations = [(c["id"], c["expression"], c["value"]) for c in answer["calculations"]]
            result = check(llm, answer["text"], sources, calculations, role=role)
            item = {
                "id": question.id,
                "checks": [asdict(c) for c in result.checks],
                "faithful": result.faithful,
                "error": result.error,
                "model": result.model,
                "prompt_version": PROMPT_VERSION,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            }
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            done[question.id] = item
            supported = sum(c.supported is True for c in result.checks)
            print(f"  {number}/{len(todo)} {question.id}: {supported}/{len(result.checks)}")

    checked = [q for q in questions if q.id in done]
    rows = []
    citations = supporting = 0
    for q in checked:
        checks = done[q.id]["checks"]
        cited = [c for c in checks if c["supported"] is not None]
        citations += sum(len(c["cited"]) for c in cited)
        supporting += sum(len(set(c["supporting"]) & set(c["cited"])) for c in cited)
        rows.append(
            {
                "id": q.id,
                "question_type": q.question_type,
                "faithful": float(done[q.id]["faithful"]),
                "supported_share": (
                    sum(c["supported"] is True for c in checks) / len(checks) if checks else 0.0
                ),
                "sentences": len(checks),
                "uncited_sentences": len(checks) - len(cited),
            }
        )
    items = [done[q.id] for q in checked]
    summary = RunSummary(
        suite="faithfulness",
        run=f"{args.run}--{name}",
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "answers_run": args.run,
            "judge_model": models[role],
            "prompt_version": PROMPT_VERSION,
            "citation_precision": round(supporting / citations, 4) if citations else None,
            "citations": citations,
            "judge_errors": sum(item["error"] is not None for item in items),
            "judge_tokens": sum(i["prompt_tokens"] + i["completion_tokens"] for i in items),
        },
        metrics=summarise(rows, METRICS),
        by={"question_type": summarise_by(rows, METRICS, "question_type")},
    )
    directory = args.results_dir / "faithfulness" / f"{args.run}--{name}" / "dev"
    write_run(directory, summary, rows)
    print({metric: round(value.mean, 3) for metric, value in summary.metrics.items()})
    print(f"citation precision {summary.system['citation_precision']}; wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
