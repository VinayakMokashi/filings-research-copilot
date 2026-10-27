"""Searching for a better HyDE prompt with DSPy (step 7.3).

HyDE asks the fast model for a passage, in a filing's own words, that would answer the
question, and the doc agent searches with it as a passage (ADR-0012). Its prompt was written
by hand. DSPy (Khattab et al., 2023) treats a prompt as a program whose instruction can be
searched for against a metric; its MIPROv2 optimiser (Opsahl-Ong et al., 2024) has a second
model propose instructions, and keeps the one that scores best on a validation set, with
Bayesian optimisation over its trials.

- **Examples** come from the synthetic pairs (`copilot.training.pairs`), about training
  filings only: a question, its filing and the chunk that answers it. The validation set is
  the pairs of the 20 filings step 7.1 held out (`copilot.training.embedder.split_filings`);
  the training set is pairs from other filings, whole filings at a time.
- **The metric** is the reciprocal rank, counted to ten, of the answering chunk among all
  of its filing's chunks when the passage is the search: bge-small, the passage embedded as
  a passage, as the doc agent searches with HyDE. 1 at the top, 0 below ten.
- **Instructions only.** Worked examples would carry the pairs' questions, which come from
  FinanceBench's filings and are never committed, so the search is over the instruction
  alone, and the result can ship as a `copilot.retrieval.rewrite.HydePrompt`. It is scored
  again in this project's own message format, then on FinanceBench dev in the doc agent's
  pipeline.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import DenseEmbedder
from copilot.retrieval.rewrite import HydePrompt
from copilot.training.pairs import Pair

TOP_K = 10
TRAIN_SIZE = 100
SEED = 0


@dataclass(frozen=True, slots=True)
class Example:
    """One pair as an optimisation example: the question, and where its answer is."""

    pair_id: int
    question: str
    doc_name: str
    chunk_id: str


def examples(pairs: Sequence[Pair]) -> list[Example]:
    return [
        Example(number, pair.question, pair.doc_name, pair.chunk_id)
        for number, pair in enumerate(pairs)
    ]


def split_examples(
    items: Sequence[Example], val_filings: Iterable[str], size: int = TRAIN_SIZE, seed: int = SEED
) -> tuple[list[Example], list[Example]]:
    """The training examples (`size` of them, from whole filings, seeded) and the validation
    examples (every example of the validation filings)."""
    held_out = set(val_filings)
    val = [item for item in items if item.doc_name in held_out]
    by_filing: dict[str, list[Example]] = {}
    for item in items:
        if item.doc_name not in held_out:
            by_filing.setdefault(item.doc_name, []).append(item)
    order = sorted(by_filing)
    random.Random(seed).shuffle(order)
    train: list[Example] = []
    for name in order:
        if len(train) >= size:
            break
        train += by_filing[name]
    return train[:size], val


def reciprocal_rank(rank: int, k: int = TOP_K) -> float:
    """1 / (rank + 1) for a 0-based rank inside the top k, else 0."""
    return 1.0 / (rank + 1) if rank < k else 0.0


class ChunkIndex:
    """The chunk vectors of some filings, for ranking a passage against one filing's chunks."""

    def __init__(self, chunks: Sequence[Chunk], vectors: NDArray[np.float32]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(vectors)} vectors for {len(chunks)} chunks.")
        self.vectors = vectors
        self.rows: dict[str, list[int]] = {}
        self.row: dict[str, int] = {}
        for row, chunk in enumerate(chunks):
            self.rows.setdefault(chunk.doc_name, []).append(row)
            self.row[chunk.chunk_id] = row

    def rank(self, vector: NDArray[np.float32], doc_name: str, chunk_id: str) -> int:
        """How many of the filing's chunks score higher than the answering one."""
        rows = self.rows[doc_name]
        scores = self.vectors[rows] @ vector
        own = float(self.vectors[self.row[chunk_id]] @ vector)
        return int(np.sum(scores > own))


def passage_score(index: ChunkIndex, embedder: DenseEmbedder, item: Example, passage: str) -> float:
    """The metric for one passage: the answering chunk's reciprocal rank, to ten."""
    if not passage.strip():
        return 0.0
    vector = embedder.embed_documents([" ".join(passage.split())])[0]
    return reciprocal_rank(index.rank(vector, item.doc_name, item.chunk_id))


def load_vectors(folder: Path, names: Iterable[str]) -> dict[str, NDArray[np.float32]]:
    """Vectors already embedded for some filings, one .npy file a filing."""
    return {
        name: np.load(folder / f"{name}.npy") for name in names if (folder / f"{name}.npy").exists()
    }


def embed_filings(
    chunks: Mapping[str, Sequence[Chunk]],
    embedder: DenseEmbedder,
    folder: Path,
    log: Callable[[str], None] = print,
) -> None:
    """Embed each filing's chunks not yet in `folder`, a filing at a time, so a stop loses
    at most one filing."""
    folder.mkdir(parents=True, exist_ok=True)
    todo = [name for name in sorted(chunks) if not (folder / f"{name}.npy").exists()]
    for number, name in enumerate(todo, start=1):
        vectors = embedder.embed_documents([chunk.text for chunk in chunks[name]])
        np.save(folder / f"{name}.npy", vectors.astype(np.float32))
        log(f"  {number}/{len(todo)} {name}: {len(chunks[name])} chunks")


def build_index(chunks: Mapping[str, Sequence[Chunk]], folder: Path) -> ChunkIndex:
    names = sorted(chunks)
    stored = load_vectors(folder, names)
    missing = [name for name in names if name not in stored]
    if missing:
        raise FileNotFoundError(f"No vectors for {len(missing)} filings, such as {missing[0]}.")
    ordered = [chunk for name in names for chunk in chunks[name]]
    return ChunkIndex(ordered, np.concatenate([stored[name] for name in names]))


def prompt_record(prompt: HydePrompt, **extra: Any) -> dict[str, Any]:
    """A HyDE prompt as `load_hyde_prompt` reads it, with notes on how it was made."""
    return {
        "version": prompt.version,
        "instruction": prompt.instruction,
        "examples": [list(example) for example in prompt.examples],
        **extra,
    }


def write_prompt(path: Path, prompt: HydePrompt, **extra: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = prompt_record(prompt, **extra)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
