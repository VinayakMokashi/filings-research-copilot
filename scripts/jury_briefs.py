"""Grade a brief run's rubrics again with a second judge, and measure how far they agree (7.6).

`poe run-briefs` grades each brief with the evaluation's judge (the `fast` role). A rubric
verdict is one model's reading, so this asks a second model, by default the `strong` role,
for the same verdicts on the same briefs and items, and reports the second judge's rubric
score, the share of items the two graded alike, and Cohen's kappa. Its calls go through
data/cache/brief-jury.jsonl, a cache no other run writes.

Writes eval/results/briefs/<run>/dev/jury.json beside the run's own grades.

Usage: uv run poe jury-briefs --run crew-v1 [--role strong]
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from copilot.config import get_settings
from copilot.eval import briefs
from copilot.eval.report import RESULTS_DIR
from copilot.eval.stats import cohens_kappa
from copilot.llm import LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="a brief run under eval/results/briefs")
    parser.add_argument("--role", default="strong", choices=("strong", "fast", "small"))
    parser.add_argument("--briefs", type=Path, default=briefs.BRIEFS, help="the brief set")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    settings = get_settings()
    models = role_models(settings)
    cases = {case.id: case for case in briefs.load_briefs(args.briefs)}
    directory = args.results_dir / "briefs" / args.run / "dev"
    rows = [
        json.loads(line)
        for line in (directory / "items.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    cache = CachedLLM(
        LLMGateway(settings), settings.data_dir / "cache" / "brief-jury.jsonl", models
    )
    llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    first: list[bool] = []
    second: list[bool] = []
    scores = []
    for row in rows:
        grade = briefs.grade(llm, cases[row["id"]], row["text"], role=args.role)
        first += [bool(met) for met in row["met"]]
        second += grade.met
        scores.append(grade.score)
        print(f"  {row['id']}: first judge {row['rubric']:.2f}, second {grade.score:.2f}")
    result = {
        "run": args.run,
        "first_judge": models["fast"],
        "second_judge": models[args.role],
        "briefs": len(rows),
        "items": len(first),
        "first_rubric": round(sum(first) / len(first), 4),
        "second_rubric": round(sum(scores) / len(scores), 4),
        "agreement": round(briefs.agreement(first, second), 4),
        "kappa": round(cohens_kappa([str(v) for v in first], [str(v) for v in second]), 4),
    }
    (directory / "jury.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
