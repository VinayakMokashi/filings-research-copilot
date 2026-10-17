"""Chunking strategies: spans, overlap, page attribution, sections and metadata."""

from __future__ import annotations

import re
import uuid
from itertools import pairwise
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from copilot.eval.financebench import Document
from copilot.ingest import chunking
from copilot.ingest.chunking import PageChunker, SemanticChunker, TokenChunker
from copilot.ingest.pdf import Page

META = Document(
    doc_name="ACME_2022_10K",
    company="Acme",
    gics_sector="Industrials",
    doc_type="10k",
    doc_period=2022,
    doc_link="https://example.com",
)


def words(text: str) -> list[tuple[int, int]]:
    """A stand-in tokenizer: one token per whitespace-separated word."""
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _sentence(n: int, length: int = 5) -> str:
    return " ".join(f"w{n}x{i}" for i in range(length - 1)) + "."


def _pages() -> list[Page]:
    first = "\n\n".join(" ".join(_sentence(p * 10 + s) for s in range(3)) for p in range(3))
    second = "Item 7. Management's Discussion\n" + " ".join(_sentence(90 + s) for s in range(6))
    return [
        Page("ACME_2022_10K", 0, first, "1", ()),
        Page("ACME_2022_10K", 1, second, "1", ((0, "7"),)),
    ]


def test_assemble_joins_pages_and_attributes_spans() -> None:
    doc = chunking.assemble(_pages(), META)

    assert doc.text == doc.pages[0].text + "\n\n" + doc.pages[1].text
    assert doc.page_starts == (0, len(doc.pages[0].text) + 2)
    boundary = doc.page_starts[1]
    assert doc.page_spans(boundary - 5, boundary + 40) == (1, 0)
    assert doc.page_spans(0, 10) == (0,)
    assert doc.section_at(0) == "1"
    assert doc.section_at(boundary) == "7"


def test_token_chunks_respect_the_limit_overlap_and_cover_everything() -> None:
    doc = chunking.assemble(_pages(), META)

    chunks = TokenChunker(words, max_tokens=12, overlap=3).chunk(doc)

    assert all(chunk.tokens <= 12 for chunk in chunks)
    assert all(b.char_start < a.char_end for a, b in pairwise(chunks))
    covered = {
        span
        for chunk in chunks
        for span in words(doc.text)
        if chunk.char_start <= span[0] < chunk.char_end
    }
    assert covered == set(words(doc.text))
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_token_chunks_end_at_the_strongest_break_in_reach() -> None:
    text = (
        " ".join(_sentence(n) for n in range(2))
        + "\n\n"
        + " ".join(_sentence(n) for n in range(2, 6))
    )
    doc = chunking.assemble([Page("ACME_2022_10K", 0, text, None, ())], META)

    first = TokenChunker(words, max_tokens=14, overlap=0).chunk(doc)[0]

    assert first.text == " ".join(_sentence(n) for n in range(2))  # ends at the blank line


def test_page_chunks_never_cross_pages() -> None:
    doc = chunking.assemble(_pages(), META)

    chunks = PageChunker(words, max_tokens=12).chunk(doc)

    assert all(len(chunk.pages) == 1 for chunk in chunks)
    assert {chunk.pages[0] for chunk in chunks} == {0, 1}
    assert all(chunk.tokens <= 12 for chunk in chunks)


def test_chunks_carry_metadata_and_stable_ids() -> None:
    doc = chunking.assemble(_pages(), META)

    first = TokenChunker(words, max_tokens=12, overlap=3).chunk(doc)
    again = TokenChunker(words, max_tokens=12, overlap=3).chunk(doc)
    last = first[-1]

    assert [c.chunk_id for c in first] == [c.chunk_id for c in again]
    assert uuid.UUID(last.point_id).hex == last.chunk_id[:32]
    assert (last.company, last.doc_period, last.doc_type, last.strategy) == (
        "Acme",
        2022,
        "10k",
        "tokens-12",
    )
    assert last.section == "7"


def _topic_embed(texts: list[str]) -> NDArray[np.float32]:
    """Revenue lines point one way, litigation lines the other."""
    return np.array(
        [[1.0, 0.0] if "revenue" in t.lower() else [0.0, 1.0] for t in texts], dtype=np.float32
    )


def test_semantic_chunks_break_where_the_topic_changes() -> None:
    revenue = "\n".join(f"Revenue line {i} grew." for i in range(5))
    litigation = "\n".join(f"Litigation line {i} continues." for i in range(5))
    doc = chunking.assemble([Page("ACME_2022_10K", 0, f"{revenue}\n{litigation}", None, ())], META)

    chunks = SemanticChunker(
        words, _topic_embed, max_tokens=100, min_tokens=1, percentile=50, unit_min_tokens=1
    ).chunk(doc)

    assert [chunk.text for chunk in chunks] == [revenue, litigation]


def test_semantic_chunker_merges_tiny_pieces() -> None:
    lines = "\n".join(f"{'Revenue' if i % 2 else 'Litigation'} item {i}." for i in range(8))
    doc = chunking.assemble([Page("ACME_2022_10K", 0, lines, None, ())], META)

    chunks = SemanticChunker(
        words, _topic_embed, max_tokens=100, min_tokens=8, percentile=10, unit_min_tokens=1
    ).chunk(doc)

    assert all(chunk.tokens >= 8 for chunk in chunks[:-1])


def test_semantic_units_join_short_sentences_and_split_long_blocks() -> None:
    seen: list[str] = []

    def record(texts: list[str]) -> NDArray[np.float32]:
        seen.extend(texts)
        return np.ones((len(texts), 2), dtype=np.float32)

    table = "\n".join(f"row{i} {i} {i}" for i in range(20))
    prose = "Short one. Short two.\nShort three."
    text = f"{prose}\n\n{table}"
    doc = chunking.assemble([Page("ACME_2022_10K", 0, text, None, ())], META)

    SemanticChunker(words, record, unit_min_tokens=4, unit_max_tokens=12).chunk(doc)

    assert seen[0] == "Short one. Short two."
    assert seen[1].startswith("Short three.\n\nrow0 0 0")
    assert all(len(words(unit)) <= 12 + 4 - 1 for unit in seen)
    assert re.sub(r"\s", "", "".join(seen)) == re.sub(r"\s", "", text)


def test_blank_spans_are_skipped(tmp_path: Path) -> None:
    pages = [
        Page("ACME_2022_10K", 0, "   ", None, ()),
        Page("ACME_2022_10K", 1, "Real text here.", None, ()),
    ]
    doc = chunking.assemble(pages, META)

    chunks = PageChunker(words).chunk(doc)
    chunking.write_chunks(chunks, tmp_path / "c.jsonl")

    assert [(c.text, c.pages) for c in chunks] == [("Real text here.", (1,))]
    assert chunking.read_chunks(tmp_path / "c.jsonl") == chunks
