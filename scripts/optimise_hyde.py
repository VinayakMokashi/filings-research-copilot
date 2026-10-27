"""Search for a better HyDE prompt with DSPy's MIPROv2, and score it (step 7.3).

1. Examples from the synthetic pairs (`copilot.training.hyde`): validation, the pairs of the
   20 filings step 7.1 held out; training, 100 pairs from other filings.
2. The chunk vectors of those filings, embedded once with bge-small (one .npy a filing in
   data/processed/dspy/vectors/, so a stop loses at most one filing).
3. The hand-written prompt (version 1) scored on both sets: each passage's reciprocal rank,
   to ten, of the chunk that answers its question, among its filing's chunks.
4. MIPROv2 searches instructions only (no worked examples: they would carry the pairs'
   questions, which are never committed), with gpt-oss-120b proposing and the fast model
   writing the passages; DSPy's own cache sits in data/cache/dspy.
5. The best instruction, exported as a `HydePrompt` (data/processed/dspy/hyde-<version>.json),
   scored again in this project's own message format on both sets.

Scores go to eval/results/dspy/hyde-<version>/<set>/ and hyde-1/<set>/, by pair number, so
`poe compare-runs` pairs them. The project's calls go through data/cache/hyde.jsonl.

Usage (the strong and fast roles on Cerebras):
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \\
  FRC_LLM_TOKENS_PER_MINUTE=100000 uv run poe optimise-hyde
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.config import get_settings
from copilot.eval.report import RESULTS_DIR, RunSummary, render_markdown, summarise, write_run
from copilot.ingest.chunking import Chunk, read_chunks
from copilot.ingest.embed import FastEmbedDense
from copilot.llm import LLMClient, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import model_params, role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import configure_logging
from copilot.retrieval import rewrite as rw
from copilot.training import embedder as data
from copilot.training import hyde
from copilot.training.pairs import load_pairs

V1_INSTRUCTION = f"{rw._SYSTEM['hyde']} {rw._TASK['hyde']}"


def score(
    llm: LLMClient,
    prompt: rw.HydePrompt | None,
    items: Sequence[hyde.Example],
    index: hyde.ChunkIndex,
    embedder: FastEmbedDense,
) -> list[dict[str, Any]]:
    """Each example's passage under `prompt` (None: version 1) and its metric."""
    rows = []
    for item in items:
        searches = rw.rewrite(llm, "hyde", item.question, prompt)
        passage = searches[0].text if searches else ""
        rows.append(
            {
                "id": f"pair-{item.pair_id:04d}",
                "doc_name": item.doc_name,
                "rr@10": hyde.passage_score(index, embedder, item, passage),
                "words": len(passage.split()),
            }
        )
    return rows


def record(
    results: Path, name: str, split: str, rows: list[dict[str, Any]], system: dict[str, Any]
) -> float:
    summary = RunSummary(
        suite="dspy",
        run=name,
        split=split,
        created=datetime.now(UTC),
        questions=len(rows),
        test_split_opened=False,
        system=system,
        metrics=summarise(rows, ["rr@10", "words"]),
    )
    write_run(results / "dspy" / name / split, summary, rows)
    print(render_markdown(summary).split("## System")[0])
    return summary.metrics["rr@10"].mean


def optimise(
    train: Sequence[hyde.Example],
    val: Sequence[hyde.Example],
    index: hyde.ChunkIndex,
    embedder: FastEmbedDense,
    cache_dir: Path,
    threads: int,
) -> str:
    """MIPROv2's best instruction for the HyDE passage, searched against the metric."""
    import dspy
    from dspy.teleprompt import MIPROv2

    settings = get_settings()
    models = role_models(settings)
    dspy.configure_cache(disk_cache_dir=str(cache_dir))

    def lm(role: str, **kwargs: Any) -> Any:
        model = models[role]  # type: ignore[index]
        key = getattr(settings, f"{model.split('/', 1)[0]}_api_key")
        secret = key.get_secret_value() if key is not None else None
        return dspy.LM(model, api_key=secret, **model_params(model), **kwargs)

    task = lm("fast", temperature=0.0, max_tokens=1024)
    proposer = lm("strong", temperature=1.0, max_tokens=4096)
    dspy.configure(lm=task)

    class HyDE(dspy.Signature):  # type: ignore[misc]
        question: str = dspy.InputField(desc="an analyst's question about a company's filing")
        passage: str = dspy.OutputField(desc="the passage of the filing that answers it")

    by_id = {item.pair_id: item for item in [*train, *val]}

    def metric(example: Any, prediction: Any, trace: Any = None) -> float:
        item = by_id[example.pair_id]
        return hyde.passage_score(index, embedder, item, str(prediction.passage or ""))

    def dataset(items: Sequence[hyde.Example]) -> list[Any]:
        return [
            dspy.Example(question=item.question, pair_id=item.pair_id).with_inputs("question")
            for item in items
        ]

    program = dspy.Predict(HyDE.with_instructions(V1_INSTRUCTION))
    optimiser = MIPROv2(
        metric=metric,
        prompt_model=proposer,
        task_model=task,
        auto="light",
        num_threads=threads,
        max_bootstrapped_demos=0,
        max_labeled_demos=0,
        seed=hyde.SEED,
        verbose=False,
    )
    compiled = optimiser.compile(
        program, trainset=dataset(train), valset=dataset(val), requires_permission_to_run=False
    )
    return str(compiled.signature.instructions)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--version", default="2", help="the new prompt's version")
    parser.add_argument("--threads", type=int, default=2, help="DSPy's parallel evaluations")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--embed-only", action="store_true", help="embed the chunks and stop")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    root = settings.data_dir / "processed"
    pairs = load_pairs(root / "synthetic" / "pairs.jsonl")
    val_filings = data.split_filings({pair.doc_name for pair in pairs})
    train, val = hyde.split_examples(hyde.examples(pairs), val_filings)
    names = sorted({item.doc_name for item in [*train, *val]})
    chunks: dict[str, list[Chunk]] = {
        name: read_chunks(root / "chunks" / "tokens-480" / f"{name}.jsonl") for name in names
    }
    print(
        f"{len(train)} training and {len(val)} validation examples, {len(names)} filings, "
        f"{sum(map(len, chunks.values()))} chunks"
    )
    embedder = FastEmbedDense(cache_dir=settings.data_dir / "models")
    folder = root / "dspy" / "vectors"
    hyde.embed_filings(chunks, embedder, folder)
    if args.embed_only:
        return 0
    index = hyde.build_index(chunks, folder)

    models = role_models(settings)
    cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "hyde.jsonl", models)
    llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    system = {"model": models["fast"], "metric": "reciprocal rank to 10, within the filing"}
    baseline = {
        split: record(
            args.results_dir,
            "hyde-1",
            split,
            score(llm, None, items, index, embedder),
            system | {"prompt_version": "1"},
        )
        for split, items in (("train", train), ("val", val))
    }

    instruction = optimise(
        train, val, index, embedder, settings.data_dir / "cache" / "dspy", args.threads
    )
    prompt = rw.HydePrompt(args.version, instruction)
    path = root / "dspy" / f"hyde-{args.version}.json"
    hyde.write_prompt(
        path,
        prompt,
        optimiser="DSPy MIPROv2, auto=light, instructions only",
        task_model=models["fast"],
        proposer_model=models["strong"],
        made=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    print(f"Wrote {path}:\n{instruction}\n")
    for split, items in (("train", train), ("val", val)):
        rows = score(llm, prompt, items, index, embedder)
        mean = record(
            args.results_dir,
            f"hyde-{args.version}",
            split,
            rows,
            system | {"prompt_version": args.version, "instruction": instruction},
        )
        print(f"{split}: version 1 {baseline[split]:.3f}, version {args.version} {mean:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
