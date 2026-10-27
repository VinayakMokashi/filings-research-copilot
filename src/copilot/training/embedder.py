"""The domain embedder's training data (step 7.1): pairs, their filings' chunks, the corpus.

`kaggle/embedder/train_embedder.py` fine-tunes bge-small on the synthetic pairs
(`copilot.training.pairs`). Its data hold filing text, from FinanceBench's filings (CC BY-NC
4.0), which this repository never commits, so the kernel reads them from a private Kaggle
dataset instead of GitHub. Three gzipped JSON Lines files:

- `pairs.jsonl.gz`: each pair's question, the chunk that answers it (with its place in the
  filing) and its split. Every pair of about a tenth of the training filings is `val`, whole
  filings at a time, so validation asks about filings the model never trained on, as the
  FinanceBench dev questions do; the rest are `train`.
- `chunks.jsonl.gz`: every 480-token chunk of the training filings, with its company. Hard
  negatives are mined from a pair's own filing and from other companies' filings, and
  validation ranks a question's chunk among its filing's chunks and among all of them.
- `pages.jsonl.gz`: the page chunks of the 84 filings behind FinanceBench's questions, which
  the kernel embeds with each model for the retrieval evaluation.

The files are written byte for byte the same on every run (sorted rows, no timestamp in the
gzip header), and `manifest` records counts and checksums of their contents, without text,
for the committed manifest and to tell when the dataset needs a new version.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import random
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from copilot.ingest.chunking import Chunk
from copilot.training.pairs import Pair

VAL_SHARE = 0.1
SEED = 0
FILES = ("pairs.jsonl.gz", "chunks.jsonl.gz", "pages.jsonl.gz")


def split_filings(names: Iterable[str], share: float = VAL_SHARE, seed: int = SEED) -> set[str]:
    """The validation filings: a seeded sample of `share` of them, at least one."""
    ordered = sorted(set(names))
    count = max(1, round(len(ordered) * share))
    return set(random.Random(seed).sample(ordered, count))


def pair_records(
    pairs: Sequence[Pair], chunks: Mapping[str, Chunk], val_filings: Collection[str]
) -> list[dict[str, Any]]:
    """One record a pair, numbered in the pairs file's order.

    KeyError names a pair whose chunk isn't among `chunks`.
    """
    records = []
    for number, pair in enumerate(pairs):
        chunk = chunks[pair.chunk_id]
        records.append(
            {
                "pair_id": number,
                "question": pair.question,
                "chunk_id": pair.chunk_id,
                "doc_name": pair.doc_name,
                "company": pair.company,
                "chunk_index": chunk.chunk_index,
                "split": "val" if pair.doc_name in val_filings else "train",
            }
        )
    return records


def chunk_record(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_name": chunk.doc_name,
        "company": chunk.company,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
    }


def page_record(chunk: Chunk) -> dict[str, Any]:
    return {"chunk_id": chunk.chunk_id, "doc_name": chunk.doc_name, "text": chunk.text}


def by_place(chunks: Iterable[Chunk]) -> list[Chunk]:
    """Chunks in a fixed order: by filing, then by place in the filing."""
    return sorted(chunks, key=lambda chunk: (chunk.doc_name, chunk.chunk_index))


def write_jsonl_gz(rows: Iterable[Mapping[str, Any]], path: Path) -> dict[str, Any]:
    """Write rows as gzipped JSON Lines; their count and the SHA-256 of the uncompressed text."""
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out:
        out.write(text)
    return {"rows": text.count(b"\n"), "sha256": hashlib.sha256(text).hexdigest()}


def manifest(
    pairs: Sequence[Mapping[str, Any]],
    files: Mapping[str, Mapping[str, Any]],
    train_filings: int,
    corpus_filings: int,
    source_pairs_sha256: str,
) -> dict[str, Any]:
    """Counts and checksums for the dataset, without any text."""
    val = [pair for pair in pairs if pair["split"] == "val"]
    return {
        "pairs": {
            "train": len(pairs) - len(val),
            "val": len(val),
            "val_filings": len({pair["doc_name"] for pair in val}),
        },
        "filings": {"train": train_filings, "corpus": corpus_filings},
        "val_share": VAL_SHARE,
        "seed": SEED,
        "files": {name: dict(files[name]) for name in FILES},
        "source_pairs_sha256": source_pairs_sha256,
    }
