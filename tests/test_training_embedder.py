"""The domain embedder's data: whole filings held out, fixed bytes, and counts without text."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from copilot.ingest.chunking import Chunk
from copilot.training import embedder
from copilot.training.pairs import Pair


def _chunk(doc: str, index: int, text: str = "Revenue rose on higher volumes.") -> Chunk:
    return Chunk(
        chunk_id=hashlib.sha256(f"{doc}|{index}".encode()).hexdigest(),
        strategy="tokens-480",
        doc_name=doc,
        chunk_index=index,
        text=text,
        char_start=index * 100,
        char_end=index * 100 + len(text),
        pages=(index,),
        section=None,
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        tokens=300,
    )


def _pair(chunk: Chunk, question: str = "Why did Acme's revenue rise in fiscal 2022?") -> Pair:
    return Pair(
        chunk_id=chunk.chunk_id,
        doc_name=chunk.doc_name,
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        question=question,
        model="test",
    )


def test_split_filings_holds_out_a_seeded_tenth_and_at_least_one() -> None:
    names = [f"F{number:03d}" for number in range(195)]

    val = embedder.split_filings(names)

    assert len(val) == 20
    assert val <= set(names)
    assert val == embedder.split_filings(reversed(names))  # order doesn't matter
    assert len(embedder.split_filings(["A", "B"])) == 1


def test_pair_records_split_by_filing_and_keep_the_chunk_place() -> None:
    chunks = [_chunk("A", 0), _chunk("A", 1), _chunk("B", 4)]
    pairs = [_pair(chunks[0]), _pair(chunks[1]), _pair(chunks[2])]

    records = embedder.pair_records(pairs, {c.chunk_id: c for c in chunks}, {"B"})

    assert [r["split"] for r in records] == ["train", "train", "val"]
    assert [r["pair_id"] for r in records] == [0, 1, 2]
    assert records[2]["chunk_index"] == 4
    assert set(records[0]) == {
        "pair_id",
        "question",
        "chunk_id",
        "doc_name",
        "chunk_index",
        "split",
    }


def test_pair_records_name_a_chunk_that_is_missing() -> None:
    chunk = _chunk("A", 0)

    with pytest.raises(KeyError):
        embedder.pair_records([_pair(chunk)], {}, set())


def test_by_place_orders_by_filing_then_place() -> None:
    chunks = [_chunk("B", 0), _chunk("A", 2), _chunk("A", 1)]

    ordered = embedder.by_place(chunks)

    assert [(c.doc_name, c.chunk_index) for c in ordered] == [("A", 1), ("A", 2), ("B", 0)]


def test_write_jsonl_gz_writes_the_same_bytes_every_time(tmp_path: Path) -> None:
    rows = [embedder.page_record(_chunk("A", 0)), embedder.page_record(_chunk("A", 1))]

    first = embedder.write_jsonl_gz(rows, tmp_path / "one" / "pages.jsonl.gz")
    second = embedder.write_jsonl_gz(rows, tmp_path / "two" / "pages.jsonl.gz")

    one = (tmp_path / "one" / "pages.jsonl.gz").read_bytes()
    assert one == (tmp_path / "two" / "pages.jsonl.gz").read_bytes()
    text = gzip.decompress(one)
    assert first == second == {"rows": 2, "sha256": hashlib.sha256(text).hexdigest()}
    assert [json.loads(line) for line in text.decode().splitlines()] == rows


def test_manifest_counts_without_text() -> None:
    records = [
        {"doc_name": "A", "split": "train"},
        {"doc_name": "B", "split": "val"},
        {"doc_name": "B", "split": "val"},
    ]
    files = {name: {"rows": 1, "sha256": "x"} for name in embedder.FILES}

    manifest = embedder.manifest(
        records, files, train_filings=2, corpus_filings=84, source_pairs_sha256="y"
    )

    assert manifest["pairs"] == {"train": 1, "val": 2, "val_filings": 1}
    assert manifest["filings"] == {"train": 2, "corpus": 84}
    assert manifest["files"] == files
    assert "question" not in json.dumps(manifest)
