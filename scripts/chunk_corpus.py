"""Chunk the parsed filings with one strategy and report what the chunks look like.

Writes data/processed/chunks/<strategy>/<doc_name>.jsonl and a summary. Strategies:
`page`, `tokens-480` and `tokens-256` (the semantic chunker needs an embedder; see
`poe index-corpus`).

Usage: uv run poe chunk-corpus --strategy tokens-480   (after `poe parse-pdfs`)
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from copilot.config import get_settings
from copilot.eval import financebench as fb
from copilot.ingest.chunking import (
    Chunker,
    PageChunker,
    TokenChunker,
    assemble,
    bge_token_offsets,
    write_chunks,
)
from copilot.ingest.corpus import pages_path
from copilot.ingest.pdf import read_pages

STRATEGIES = ("page", "tokens-480", "tokens-256")


def make_chunker(strategy: str) -> Chunker:
    offsets = bge_token_offsets()
    if strategy == "page":
        return PageChunker(offsets, max_tokens=480)
    if strategy == "tokens-480":
        return TokenChunker(offsets, max_tokens=480, overlap=64)
    if strategy == "tokens-256":
        return TokenChunker(offsets, max_tokens=256, overlap=32)
    raise ValueError(f"Unknown strategy {strategy!r}; choose from {', '.join(STRATEGIES)}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--strategy", choices=STRATEGIES, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    documents = fb.load_documents(settings.data_dir / "raw" / "financebench")
    pages_dir = settings.data_dir / "processed" / "pages"
    out_dir = settings.data_dir / "processed" / "chunks" / args.strategy
    chunker = make_chunker(args.strategy)

    started = time.perf_counter()
    tokens: list[int] = []
    multi_page = 0
    docs = 0
    for path in sorted(pages_dir.glob("*.jsonl")):
        if path.stem not in documents:
            continue  # PDFs missing from FinanceBench's document file have no metadata
        chunks = chunker.chunk(
            assemble(read_pages(pages_path(pages_dir, path.stem)), documents[path.stem])
        )
        write_chunks(chunks, out_dir / f"{path.stem}.jsonl")
        tokens += [chunk.tokens for chunk in chunks]
        multi_page += sum(len(chunk.pages) > 1 for chunk in chunks)
        docs += 1
    elapsed = time.perf_counter() - started

    summary = {
        "strategy": args.strategy,
        "documents": docs,
        "chunks": len(tokens),
        "mean_tokens": round(statistics.mean(tokens), 1),
        "median_tokens": statistics.median(tokens),
        "max_tokens": max(tokens),
        "multi_page_share": round(multi_page / len(tokens), 3),
    }
    (out_dir / "_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Chunked {docs} documents in {elapsed:.0f} s: {json.dumps(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
