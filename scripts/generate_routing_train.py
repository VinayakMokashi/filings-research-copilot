"""Write and label training questions for a classifier router (step 7.2).

Three stages, each resumable:

1. **Write.** The strong model writes questions batch by batch, route by route
   (`copilot.agents.router_training`), at temperature 0.9 with each batch's number as its
   seed. Replies go to data/processed/routing-train/batches-<prompt version>.jsonl as they
   arrive; a rerun skips the batches already there.
2. **Filter.** Exact repeats and near-duplicates go, and so does every question within
   LEAK_LIMIT of a routing-set question, dev or test, by bge-small similarity. The test
   split is read for this check only: no question's text is printed, and nothing is scored
   on it.
3. **Label.** The LLM router as deployed (its current prompt, on the strong role) routes each kept
   question, with a cache file of its own (data/cache/router-teacher.jsonl), so a rerun
   costs nothing. A reply that isn't a routing decision drops the question. The teacher
   also routes the routing set's dev questions, to show it still routes them as ADR-0017
   measured on the provider it runs on now.

Writes data/reference/routing_train.jsonl (committed: the project's own questions, one
line each with the teacher's route, the intended one, the style, the kind of question, the
teacher's reason and the split) and data/reference/routing_train_manifest.json (counts,
agreement, the leak check's numbers, tokens and cost, and a checksum).

Usage: uv run poe generate-routing-train --per-route 400
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from copilot.agents.router import PROMPT_VERSION as ROUTER_PROMPT_VERSION
from copilot.agents.router import ROUTES, LLMRouter, Route
from copilot.agents.router_training import (
    DUPLICATE_LIMIT,
    LEAK_LIMIT,
    PROMPT_VERSION,
    Batch,
    TrainQuestion,
    assign_splits,
    batch_plan,
    keep_distinct,
    nearest_similarity,
    parse_questions,
    writer_messages,
)
from copilot.config import get_settings
from copilot.eval.routing import load_queries
from copilot.facts.metrics import METRICS
from copilot.ingest.embed import FastEmbedDense, normalise
from copilot.llm import LLMError, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models, token_cost
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging

COMPANIES_FILE = Path("data/reference/companies.csv")
REFERENCE_DIR = Path("data/reference")
OUT_NAME = "routing_train.jsonl"
MANIFEST_NAME = "routing_train_manifest.json"


def read_batches(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {record["batch"]: record for record in records}


def write_stage(llm: PacedLLM, plan: list[Batch], path: Path) -> dict[int, dict[str, Any]]:
    done = read_batches(path)
    todo = [batch for batch in plan if batch.number not in done]
    print(f"write: {len(plan)} batches, {len(done)} done, {len(todo)} to go")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for batch in todo:
            response = llm.complete(
                writer_messages(batch),
                role="strong",
                temperature=0.9,
                max_tokens=4096,
                seed=batch.number,
                response_format={"type": "json_object"},
            )
            try:
                questions = parse_questions(response.text)
            except ValueError as exc:
                print(f"  batch {batch.number} ({batch.route}): {exc}", file=sys.stderr)
                questions = []
            record = {
                "batch": batch.number,
                "route": batch.route,
                "style": batch.style,
                "kind": batch.kind,
                "questions": questions,
                "model": response.model,
                "prompt_version": PROMPT_VERSION,
                "tokens": [response.prompt_tokens or 0, response.completion_tokens or 0],
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            done[batch.number] = record
            print(f"  batch {batch.number} {batch.route:9} {len(questions)} questions", flush=True)
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--per-route", type=int, default=400, help="questions a route to ask for")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reference-dir", type=Path, default=REFERENCE_DIR, help="output folder")
    parser.add_argument(
        "--pause", type=float, default=3.0, help="seconds after each model call (3 for free tiers)"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    models = role_models(settings)
    gateway = LLMGateway(settings)
    work = settings.data_dir / "processed" / "routing-train"
    writer = PacedLLM(
        CachedLLM(gateway, settings.data_dir / "cache" / "routing-train.jsonl", models),
        pause_s=args.pause,
        tokens_per_minute=settings.llm_tokens_per_minute,
    )
    teacher_llm = PacedLLM(
        CachedLLM(gateway, settings.data_dir / "cache" / "router-teacher.jsonl", models),
        pause_s=args.pause,
        tokens_per_minute=settings.llm_tokens_per_minute,
    )

    with COMPANIES_FILE.open(encoding="utf-8") as handle:
        companies = [row["name"] for row in csv.DictReader(handle)]
    plan = batch_plan(companies, [m.label for m in METRICS], args.per_route, seed=args.seed)

    # 1. Write.
    try:
        batches = write_stage(writer, plan, work / f"batches-{PROMPT_VERSION}.jsonl")
    except LLMError as exc:
        print(f"Stopped while writing: {exc}", file=sys.stderr)
        return 1

    # 2. Filter.
    written: list[tuple[str, Route, str, str]] = []
    seen: set[str] = set()
    for batch in sorted(batches.values(), key=lambda record: record["batch"]):
        for question in batch["questions"]:
            key = question.casefold()
            if key not in seen:
                seen.add(key)
                written.append((question, batch["route"], batch["style"], batch.get("kind", "")))
    embedder = FastEmbedDense()
    vectors = normalise(embedder.embed_documents([q for q, _, _, _ in written]))
    distinct = keep_distinct(vectors, DUPLICATE_LIMIT)
    routing = load_queries("dev") + load_queries("test", allow_test=True)
    routing_vectors = normalise(embedder.embed_documents([q.query for q in routing]))
    nearest = nearest_similarity(vectors[distinct], routing_vectors)
    kept = [i for i, score in zip(distinct, nearest, strict=True) if score < LEAK_LIMIT]
    leaked_by_route = Counter(
        written[i][1] for i, score in zip(distinct, nearest, strict=True) if score >= LEAK_LIMIT
    )
    kept_nearest = nearest[nearest < LEAK_LIMIT]
    print(
        f"filter: {sum(len(b['questions']) for b in batches.values())} written, "
        f"{len(written)} unique, {len(distinct)} distinct, {len(kept)} clear of the routing set"
    )

    # 3. Label.
    teacher = LLMRouter(teacher_llm, role="strong")
    labelled: list[tuple[int, Route, str]] = []
    errors = 0
    teacher_tokens = [0, 0]
    try:
        for count, index in enumerate(kept, start=1):
            decision = teacher.route(written[index][0])
            teacher_tokens[0] += decision.prompt_tokens
            teacher_tokens[1] += decision.completion_tokens
            if decision.error:
                errors += 1
                continue
            labelled.append((index, decision.route, decision.reason or ""))
            if count % 200 == 0:
                print(f"  labelled {count}/{len(kept)}")
        # The teacher on the routing dev questions: it should route them as ADR-0017 found.
        dev = load_queries("dev")
        dev_right = sum(teacher.route(q.query).route == q.route for q in dev)
    except LLMError as exc:
        print(f"Stopped while labelling: {exc}", file=sys.stderr)
        return 1
    print(f"teacher on routing dev: {dev_right}/{len(dev)}")

    splits = assign_splits([route for _, route, _ in labelled], seed=args.seed)
    rows = [
        TrainQuestion(
            id=f"t{number:04d}",
            question=written[index][0],
            route=route,
            intended=written[index][1],
            style=written[index][2],
            kind=written[index][3],
            reason=reason,
            split=split,
        )
        for number, ((index, route, reason), split) in enumerate(
            zip(labelled, splits, strict=True), start=1
        )
    ]
    text = "".join(json.dumps(row.model_dump(), ensure_ascii=False) + "\n" for row in rows)
    out_file = args.reference_dir / OUT_NAME
    manifest_file = args.reference_dir / MANIFEST_NAME
    out_file.write_text(text, encoding="utf-8", newline="\n")

    agree = Counter(row.intended for row in rows if row.intended == row.route)
    intended = Counter(row.intended for row in rows)
    write_tokens = [sum(b["tokens"][i] for b in batches.values()) for i in (0, 1)]
    manifest = {
        "rows": len(rows),
        "by_route": {route: sum(row.route == route for row in rows) for route in ROUTES},
        "by_split": dict(Counter(row.split for row in rows)),
        "by_kind": {
            route: dict(Counter(row.kind for row in rows if row.intended == route))
            for route in ROUTES
        },
        "intended_agrees_with_teacher": {
            route: f"{agree[route]}/{intended[route]}" for route in ROUTES
        },
        "teacher_errors": errors,
        "written": sum(len(b["questions"]) for b in batches.values()),
        "unique": len(written),
        "distinct": len(distinct),
        "leaked": len(distinct) - len(kept),
        "leaked_by_route": {route: leaked_by_route[route] for route in ROUTES},
        "leak_limit": LEAK_LIMIT,
        "duplicate_limit": DUPLICATE_LIMIT,
        "nearest_routing_similarity": {
            "median": round(float(np.median(kept_nearest)), 3) if len(kept_nearest) else None,
            "p95": round(float(np.quantile(kept_nearest, 0.95)), 3) if len(kept_nearest) else None,
            "max": round(float(np.max(kept_nearest)), 3) if len(kept_nearest) else None,
        },
        "writer": {
            "model": models["strong"],
            "prompt_version": PROMPT_VERSION,
            "batches": len(batches),
            "tokens": write_tokens,
            "cost_usd": token_cost(models["strong"], *write_tokens),
        },
        "teacher": {
            "model": models["strong"],
            "router": "llm",
            "prompt_version": ROUTER_PROMPT_VERSION,
            "tokens": teacher_tokens,
            "cost_usd": token_cost(models["strong"], *teacher_tokens),
            "routing_dev_right": f"{dev_right}/{len(dev)}",
        },
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: manifest[k] for k in ("rows", "by_route", "leaked", "teacher_errors")}))
    print(f"Wrote {out_file} and {manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
