"""Write the brief set's briefs with the crew or one specialist, and grade them (step 7.6).

Systems:
- `crew`: the brief crew (`copilot.agents.brief`), as the copilot's brief route runs it;
- `doc` and `hybrid`: the doc agent or the hybrid answering the whole request at once, the
  copilot's single agents, checked and cut by the same critic as the crew's sections.

Each brief is written once and kept, with its sources' text, in
data/processed/briefs/<run>.jsonl (git-ignored: filing text is CC BY-NC 4.0), so a rerun
picks up where it stopped. Then every brief is graded: the rubric judge
(`copilot.eval.briefs`) and the faithfulness check (`copilot.eval.faithfulness`), both on the
`fast` role, the evaluation's judge, which writes none of the briefs; each section and the
summary are checked against the sources their sentences cite. The grades go to
eval/results/briefs/<run>/dev/, with each brief's text but none of its sources' text.

Usage (the strong and fast roles on Cerebras, as ADR-0024's runs; the small role, the
critic, stays on Groq):
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \\
  FRC_LLM_TOKENS_PER_MINUTE=25000 uv run poe run-briefs --system crew --run crew-v1
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.agents.brief import Brief, BriefCrew, Section, SectionPlan
from copilot.agents.build import build_components
from copilot.agents.graph import usage
from copilot.answer.context import Source
from copilot.answer.generate import Answer
from copilot.config import get_settings
from copilot.eval import briefs
from copilot.eval.faithfulness import check
from copilot.eval.report import RESULTS_DIR, RunSummary, render_markdown, summarise, write_run
from copilot.llm import LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models, token_cost
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging

SYSTEMS = ("crew", "doc", "hybrid")
METRICS = ("rubric", "faithful_share", "faithful", "sources", "words", "cost_usd", "seconds")


def source_record(source: Source, number: int | None = None) -> dict[str, Any]:
    record = asdict(source)
    if number is not None:
        record["number"] = number
    return record


def part(
    heading: str, text: str, sources: Sequence[Source], answer: Answer | None
) -> dict[str, Any]:
    """One checkable piece of a brief: its text and the sources its citations number."""
    return {
        "heading": heading,
        "text": text,
        "sources": [source_record(source) for source in sources],
        "calculations": [asdict(c) for c in answer.calculations] if answer else [],
    }


def crew_record(written: Brief) -> dict[str, Any]:
    pieces = [
        part(section.plan.heading, text, written.sources, section.answer)
        for section, text in zip(written.answered, written.texts, strict=True)
    ]
    if written.summary:
        pieces.insert(0, part("Summary", written.summary, written.sources, None))
    return {
        "text": written.markdown(),
        "parts": pieces,
        "planned": written.planned,
        "modules": written.plan.modules,
        "sections": [
            {
                "heading": s.plan.heading,
                "question": s.plan.question,
                "route": s.plan.route,
                "answered": s.answered,
                "supported": s.supported,
                "cut": len(s.dropped),
                "error": s.error,
            }
            for s in written.sections
        ],
        "summary_cut": len(written.summary_dropped),
    }


def one_shot_record(crew: BriefCrew, system: str, request: str) -> dict[str, Any]:
    """A specialist's answer to the whole request, checked and cut by the crew's critic."""
    plan = SectionPlan(
        heading="Answer", question=request, route="hybrid" if system == "hybrid" else "doc"
    )
    section: Section = crew.write_section(plan)
    answer = section.answer
    pieces = [part("Answer", answer.text, answer.cited_sources, answer)] if section.answered else []
    return {
        "text": answer.text if section.answered else "",
        "parts": pieces,
        "sections": [
            {
                "heading": "Answer",
                "question": request,
                "route": plan.route,
                "answered": section.answered,
                "supported": section.supported,
                "cut": len(section.dropped),
                "error": section.error,
            }
        ],
    }


def spent(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> float | None:
    costs = []
    for model, (prompt, completion) in after.items():
        old_prompt, old_completion = before.get(model, (0, 0))
        if (prompt, completion) != (old_prompt, old_completion):
            costs.append(token_cost(model, prompt - old_prompt, completion - old_completion))
    known = [cost for cost in costs if cost is not None]
    return round(sum(known), 6) if len(known) == len(costs) else None


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {record["id"]: record for record in records}


def write_briefs(
    cases: Sequence[briefs.BriefCase], system: str, path: Path
) -> dict[str, dict[str, Any]]:
    """Write the briefs not yet in `path`, one at a time, each as it is finished."""
    done = read_jsonl(path)
    todo = [case for case in cases if case.id not in done]
    print(f"{len(done)} briefs already written, {len(todo)} to go")
    if not todo:
        return done
    parts = build_components(get_settings(), batch=True)
    crew = parts.brief
    assert isinstance(crew, BriefCrew)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for number, case in enumerate(todo, start=1):
            before = usage(parts.meters)
            started = datetime.now(UTC)
            if system == "crew":
                record = crew_record(crew.run(case.request))
            else:
                record = one_shot_record(crew, system, case.request)
            seconds = (datetime.now(UTC) - started).total_seconds()
            record = {
                "id": case.id,
                "system": system,
                "request": case.request,
                **record,
                "seconds": round(seconds, 1),
                "tokens_by_model": {m: list(t) for m, t in usage(parts.meters).items()},
                "cost_usd": spent(before, usage(parts.meters)),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            done[case.id] = record
            answered = sum(s["answered"] for s in record["sections"])
            print(
                f"  {number}/{len(todo)} {case.id}: {answered}/{len(record['sections'])} sections"
            )
    return done


def grade_briefs(
    cases: Sequence[briefs.BriefCase], written: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Each brief's rubric grade and faithfulness, by the evaluation's judge."""
    settings = get_settings()
    models = role_models(settings)
    judge = PacedLLM(
        CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "brief-judge.jsonl", models),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    checker = PacedLLM(
        CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "faithfulness.jsonl", models),
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    rows = []
    for case in cases:
        record = written[case.id]
        grade = briefs.grade(judge, case, record["text"])
        sentences = supported = 0
        for piece in record["parts"]:
            sources = {s["number"]: (s["label"], s["text"]) for s in piece["sources"]}
            calculations = [(c["id"], c["expression"], c["value"]) for c in piece["calculations"]]
            result = check(checker, piece["text"], sources, calculations)
            sentences += len(result.checks)
            supported += result.supported_sentences
        cited = {(s["doc_name"], s["page"]) for piece in record["parts"] for s in piece["sources"]}
        rows.append(
            {
                "id": case.id,
                "company": case.company,
                "system": record["system"],
                "rubric": round(grade.score, 4),
                "met": grade.met,
                "reasons": grade.reasons,
                "judge": grade.model,
                "judge_error": grade.error,
                "sentences": sentences,
                "supported": supported,
                "faithful_share": round(supported / sentences, 4) if sentences else 0.0,
                "faithful": float(bool(sentences) and supported == sentences),
                "sources": len(cited),
                "words": len(record["text"].split()),
                "sections": record["sections"],
                "cost_usd": record["cost_usd"] or 0.0,
                "seconds": record["seconds"],
                "text": record["text"],
            }
        )
        print(f"  {case.id}: rubric {grade.score:.2f}, supported {supported}/{sentences}")
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--system", choices=SYSTEMS, required=True)
    parser.add_argument("--run", required=True, help="run name")
    parser.add_argument("--limit", type=int, help="only the first N briefs")
    parser.add_argument("--briefs", type=Path, default=briefs.BRIEFS, help="the brief set")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    cases = briefs.load_briefs(args.briefs)[: args.limit]

    path = settings.data_dir / "processed" / "briefs" / f"{args.run}.jsonl"
    written = write_briefs(cases, args.system, path)
    rows = grade_briefs(cases, written)
    models = role_models(settings)
    summary = RunSummary(
        suite="briefs",
        run=args.run,
        split="dev",
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system={
            "system": args.system,
            "planner_and_editor": models["strong"],
            "writers": {"doc": models["strong"], "hybrid": models["strong"]},
            "critic": models["small"],
            "judge": models["fast"],
            "rubric_prompt_version": briefs.PROMPT_VERSION,
            "briefs": len(cases),
            "rubric_items": sum(len(case.rubric) for case in cases),
        },
        metrics=summarise(rows, METRICS),
    )
    directory = args.results_dir / "briefs" / args.run / "dev"
    write_run(directory, summary, rows)
    print(render_markdown(summary))
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
