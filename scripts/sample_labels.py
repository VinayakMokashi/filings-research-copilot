"""Pick the answers a person labels by hand to check the judge (step 3.6).

Draws `--size` dev questions, stratified by question type, with a fixed seed, once: the
sample doesn't depend on the answers, so the agent can answer it first. Each later run
rebuilds the labelling items from the sampled questions answered so far. Refusals get no
label (a refusal needs no judge), so the sample is a little larger than the labels wanted.
Writes:

- eval/labels/answer-correctness-sample.json: the run, seed and ids (committed);
- data/processed/labels/<run>/items.json: what the labeller sees for each answered id,
  which is what the judge sees: the question, the reference answer, how it was reached,
  the answer without its citation markers, and the computed comparisons of their figures
  (local: benchmark text and model answers).

The judge's verdicts are never shown to the labeller.

Usage: uv run poe label-sample --run doc-agent-v3-full --size 44
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from copilot.config import get_settings
from copilot.eval.judge import comparisons, strip_citations
from copilot.eval.labels import stratified_sample
from copilot.eval.splits import load_split

SAMPLE_FILE = Path("eval/labels/answer-correctness-sample.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--run", required=True, help="the answers run to sample from")
    parser.add_argument("--size", type=int, default=44)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--redraw", action="store_true", help="draw a new sample")
    args = parser.parse_args(argv)

    settings = get_settings()
    questions = load_split("dev", settings.data_dir / "raw" / "financebench")
    path = settings.data_dir / "processed" / "answers" / args.run / "dev" / "answers.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    answers = {item["id"]: item for item in (json.loads(line) for line in lines if line.strip())}
    if SAMPLE_FILE.exists() and not args.redraw:
        ids = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))["ids"]
    else:
        groups: dict[str, list[str]] = defaultdict(list)
        for question in questions:
            groups[question.question_type].append(question.id)
        picked = stratified_sample(groups, args.size, args.seed)
        ids = [question.id for question in questions if question.id in picked]
        SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        sample = {"answers_run": args.run, "seed": args.seed, "size": len(ids), "ids": ids}
        text = json.dumps(sample, indent=2) + "\n"
        SAMPLE_FILE.write_text(text, encoding="utf-8", newline="\n")

    by_id = {question.id: question for question in questions}
    items = [
        {
            "id": qid,
            "order": number,
            "question_type": by_id[qid].question_type,
            "question": by_id[qid].question,
            "reference": by_id[qid].answer,
            "justification": by_id[qid].justification or "",
            "answer": strip_citations(answers[qid]["text"]),
            "comparisons": comparisons(by_id[qid].answer, strip_citations(answers[qid]["text"])),
        }
        for number, qid in enumerate(ids, start=1)
        if answers.get(qid, {}).get("answerable")
    ]
    local = settings.data_dir / "processed" / "labels" / args.run / "items.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shares = Counter(by_id[qid].question_type for qid in ids)
    print(f"Sample of {len(ids)}: {dict(sorted(shares.items()))}; {len(items)} answered so far")
    print(f"-> {SAMPLE_FILE} and {local}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
