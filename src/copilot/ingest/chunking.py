"""Split parsed filings into chunks for retrieval (step 2.2).

A document is the concatenation of its pages, separated by blank lines, so every chunk is a
character span of it. Each chunk records the pages it touches, ordered by how much of the
chunk falls on each, plus the section at its start and the document's company, fiscal
period and form.

Three strategies, all measured in the embedding model's own tokens so that no chunk is cut
off by its 512-token limit:

- `page`: chunks never cross a page; a long page is split into windows within it.
- `tokens`: windows of up to `max_tokens` that cross pages, with `overlap` tokens repeated
  between neighbours. A window ends at the strongest break near its end (a blank line, then
  a line end, then a sentence end), falling back to a hard cut inside very long paragraphs.
- `semantic`: breaks where the meaning shifts, measured as the cosine distance between the
  embeddings of consecutive lines or sentences; a distance above the document's 90th
  percentile starts a new chunk. Pieces under `min_tokens` join the next one (otherwise every
  table row would stand alone), and oversized pieces are split like `tokens`.

Late chunking needs token embeddings from the model, so it lives with the embedders.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from copilot.eval.financebench import Document
from copilot.ingest.pdf import Page

PAGE_SEPARATOR = "\n\n"
# Break strengths, strongest first: a blank line, a line end, a sentence end.
_BREAKS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\n\s*\n"),
    re.compile(r"\n"),
    re.compile(r"(?<=[.!?;:])\s+"),
)
_UNIT_SPLIT = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9(\"'])")


class TokenOffsets(Protocol):
    """Anything that can report the character span of each token in a text."""

    def __call__(self, text: str) -> list[tuple[int, int]]: ...


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    strategy: str
    doc_name: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    pages: tuple[int, ...]
    section: str | None
    company: str
    doc_period: int
    doc_type: str
    tokens: int

    @property
    def point_id(self) -> str:
        """A UUID made from the chunk id, as vector databases want."""
        return str(uuid.UUID(self.chunk_id[:32]))


@dataclass(frozen=True, slots=True)
class AssembledDocument:
    """A document's pages joined into one text, with where each page starts."""

    name: str
    text: str
    page_starts: tuple[int, ...]
    pages: tuple[Page, ...]
    meta: Document

    def page_spans(self, start: int, end: int) -> tuple[int, ...]:
        """Pages overlapping [start, end), the page holding most of the span first."""
        overlap: dict[int, int] = {}
        first = max(bisect.bisect_right(self.page_starts, start) - 1, 0)
        for index in range(first, len(self.pages)):
            page_start = self.page_starts[index]
            if page_start >= end:
                break
            page_end = page_start + len(self.pages[index].text)
            covered = min(end, page_end) - max(start, page_start)
            if covered > 0:
                overlap[self.pages[index].page] = covered
        return tuple(sorted(overlap, key=lambda page: (-overlap[page], page)))

    def section_at(self, offset: int) -> str | None:
        index = max(bisect.bisect_right(self.page_starts, offset) - 1, 0)
        return self.pages[index].section_at(offset - self.page_starts[index])


def assemble(pages: Sequence[Page], meta: Document) -> AssembledDocument:
    starts, parts, position = [], [], 0
    for page in pages:
        starts.append(position)
        parts.append(page.text)
        position += len(page.text) + len(PAGE_SEPARATOR)
    return AssembledDocument(
        meta.doc_name, PAGE_SEPARATOR.join(parts), tuple(starts), tuple(pages), meta
    )


class Chunker(Protocol):
    @property
    def name(self) -> str: ...

    def chunk(self, doc: AssembledDocument) -> list[Chunk]: ...


def _make_chunks(
    doc: AssembledDocument, strategy: str, spans: Sequence[tuple[int, int, int]]
) -> list[Chunk]:
    """Chunks from (start, end, tokens) spans, skipping spans with no words."""
    chunks: list[Chunk] = []
    for start, end, tokens in spans:
        text = doc.text[start:end].strip()
        if not re.search(r"\w", text):
            continue
        lead = len(doc.text[start:end]) - len(doc.text[start:end].lstrip())
        start += lead
        end = start + len(text)
        digest = hashlib.sha256(f"{strategy}|{doc.name}|{start}|{end}|{text}".encode()).hexdigest()
        chunks.append(
            Chunk(
                chunk_id=digest,
                strategy=strategy,
                doc_name=doc.name,
                chunk_index=len(chunks),
                text=text,
                char_start=start,
                char_end=end,
                pages=doc.page_spans(start, end),
                section=doc.section_at(start),
                company=doc.meta.company,
                doc_period=doc.meta.doc_period,
                doc_type=doc.meta.doc_type,
                tokens=tokens,
            )
        )
    return chunks


def _break_points(text: str) -> list[tuple[int, int]]:
    """(position, strength) for every candidate break; 0 is the strongest."""
    found: dict[int, int] = {}
    for strength, pattern in enumerate(_BREAKS):
        for match in pattern.finditer(text):
            position = match.end()
            found[position] = min(found.get(position, strength), strength)
    return sorted(found.items())


def window_spans(
    text: str, offsets: Sequence[tuple[int, int]], max_tokens: int, overlap: int, base: int = 0
) -> list[tuple[int, int, int]]:
    """Token windows over `text` as (start, end, tokens), ending at the strongest nearby break."""
    if not offsets:
        return []
    token_starts = [start for start, _ in offsets]
    breaks = _break_points(text)
    break_positions = [position for position, _ in breaks]
    spans: list[tuple[int, int, int]] = []
    first = 0
    while first < len(offsets):
        last = min(first + max_tokens, len(offsets))  # exclusive token index
        end_char = offsets[last - 1][1]
        if last < len(offsets):
            # Look for a break in the window's second half: the strongest, then the latest.
            low = offsets[first + max(1, (last - first) // 2)][0]
            lo = bisect.bisect_left(break_positions, low)
            hi = bisect.bisect_right(break_positions, offsets[last][0])
            candidates = breaks[lo:hi]
            if candidates:
                position = min(candidates, key=lambda b: (b[1], -b[0]))[0]
                last = max(bisect.bisect_left(token_starts, position), first + 1)
                end_char = offsets[last - 1][1]
        spans.append((base + offsets[first][0], base + end_char, last - first))
        if last >= len(offsets):
            break
        next_first = max(last - overlap, first + 1)
        if overlap:
            # Start the overlap at a break if one falls inside it.
            lo = bisect.bisect_left(break_positions, offsets[next_first][0])
            hi = bisect.bisect_left(break_positions, offsets[last - 1][1])
            if lo < hi:
                position = min(breaks[lo:hi], key=lambda b: (b[1], b[0]))[0]
                next_first = max(bisect.bisect_left(token_starts, position), first + 1)
        first = next_first
    return spans


@dataclass(frozen=True, slots=True)
class TokenChunker:
    """Windows of up to `max_tokens` that may cross pages, overlapping by `overlap` tokens."""

    offsets: TokenOffsets
    max_tokens: int = 480
    overlap: int = 64

    @property
    def name(self) -> str:
        return f"tokens-{self.max_tokens}"

    def chunk(self, doc: AssembledDocument) -> list[Chunk]:
        spans = window_spans(doc.text, self.offsets(doc.text), self.max_tokens, self.overlap)
        return _make_chunks(doc, self.name, spans)


@dataclass(frozen=True, slots=True)
class PageChunker:
    """One chunk per page, split into windows within the page when it is too long."""

    offsets: TokenOffsets
    max_tokens: int = 480
    name: str = "page"

    def chunk(self, doc: AssembledDocument) -> list[Chunk]:
        spans: list[tuple[int, int, int]] = []
        for start, page in zip(doc.page_starts, doc.pages, strict=True):
            spans += window_spans(
                page.text, self.offsets(page.text), self.max_tokens, 0, base=start
            )
        return _make_chunks(doc, self.name, spans)


Embed = Callable[[list[str]], NDArray[np.float32]]


@dataclass(frozen=True, slots=True)
class SemanticChunker:
    """Breaks where consecutive units' embeddings drift apart; see the module docstring."""

    offsets: TokenOffsets
    embed: Embed
    max_tokens: int = 480
    min_tokens: int = 64
    percentile: float = 90.0
    name: str = "semantic"

    def chunk(self, doc: AssembledDocument) -> list[Chunk]:
        units = [(m.start(), m.end()) for m in re.finditer(r"[^\n]+", doc.text)]
        units = [span for unit in units for span in _sentences(doc.text, *unit)]
        if not units:
            return []
        vectors = self.embed([doc.text[start:end] for start, end in units])
        if len(units) > 1:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            unit_vectors = vectors / np.maximum(norms, 1e-12)
            distances = 1.0 - np.sum(unit_vectors[:-1] * unit_vectors[1:], axis=1)
            threshold = float(np.percentile(distances, self.percentile))
            cuts = [i + 1 for i, distance in enumerate(distances) if distance > threshold]
        else:
            cuts = []
        groups = [
            (units[group_start][0], units[group_end - 1][1])
            for group_start, group_end in zip([0, *cuts], [*cuts, len(units)], strict=True)
        ]
        spans: list[tuple[int, int, int]] = []
        for start, end in self._merge_small(doc.text, groups):
            piece = doc.text[start:end]
            spans += window_spans(piece, self.offsets(piece), self.max_tokens, 0, base=start)
        return _make_chunks(doc, self.name, spans)

    def _merge_small(self, text: str, groups: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Join each group to the next until it holds at least `min_tokens` tokens."""
        merged: list[tuple[int, int]] = []
        current: tuple[int, int] | None = None
        for start, end in groups:
            if current is None:
                current = (start, end)
            elif len(self.offsets(text[current[0] : current[1]])) < self.min_tokens:
                current = (current[0], end)
            else:
                merged.append(current)
                current = (start, end)
        if current is not None:
            merged.append(current)
        return merged


def _sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """A line split at sentence ends; short lines stay whole."""
    pieces, cursor = [], start
    for match in _UNIT_SPLIT.finditer(text, start, end):
        if match.start() > cursor:
            pieces.append((cursor, match.start()))
        cursor = match.end()
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


def write_chunks(chunks: Sequence[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for chunk in chunks:
            out.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def read_chunks(path: Path) -> list[Chunk]:
    with path.open(encoding="utf-8") as lines:
        records = [json.loads(line) for line in lines if line.strip()]
    return [Chunk(**{**r, "pages": tuple(r["pages"])}) for r in records]


def bge_token_offsets(model: str = "BAAI/bge-small-en-v1.5") -> TokenOffsets:
    """Token character spans from the embedding model's own tokenizer (downloaded once)."""
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_pretrained(model)

    def offsets(text: str) -> list[tuple[int, int]]:
        return [
            span
            for span in tokenizer.encode(text, add_special_tokens=False).offsets
            if span[1] > span[0]
        ]

    return offsets
