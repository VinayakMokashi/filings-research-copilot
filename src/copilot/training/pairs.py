"""Synthetic question-to-chunk pairs for fine-tuning the embedder (step 2.6, used in Phase 7).

An LLM reads one chunk of a training filing and writes a question an analyst might ask
that the chunk answers. Phase 7 trains bge-small on these pairs with in-batch negatives
(MultipleNegativesRankingLoss) and hard negatives mined from the same filing.

Training filings leave out every filing of a test company (ADR-0006) and every filing a dev
question uses, so a model trained on the pairs can still be compared fairly on dev. Chunks
are sampled evenly across filings, skipping ones too short to hold an answer and ones that
are mostly figures, such as tables and exhibit lists.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from copilot.eval.financebench import Document
from copilot.ingest.chunking import Chunk
from copilot.llm import Message, system, user

PROMPT_VERSION = "1"
MIN_TOKENS = 200
MIN_LETTER_SHARE = 0.55
QUESTION_WORDS = (8, 45)
COPIED_WORDS = 8  # a question sharing this many consecutive words with its chunk is copied

FORMS = {
    "10k": "Form 10-K annual report",
    "10k_annualreport": "annual report to shareholders",
    "10q": "Form 10-Q quarterly report",
    "8k": "Form 8-K current report",
    "Earnings": "earnings release",
}

SYSTEM_PROMPT = """\
You write questions that equity analysts ask about company filings. You are given one \
excerpt from a filing. Write one question that the excerpt answers.

Rules:
- The excerpt must contain the answer, and the question must make sense to someone who \
hasn't seen it.
- Name the company and the fiscal period, as an analyst would.
- Use your own words rather than copying sentences from the excerpt.
- Ask about a specific fact, figure, cause, risk or change, not about the excerpt or the \
document itself.
- Return only the question, on one line."""


class Pair(BaseModel):
    """One generated question and the chunk that answers it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    doc_name: str
    company: str
    doc_period: int
    doc_type: str
    question: str
    model: str
    prompt_version: str = PROMPT_VERSION


def training_documents(
    documents: Mapping[str, Document],
    test_companies: Collection[str],
    dev_documents: Collection[str],
    available: Collection[str],
) -> list[str]:
    """Filings that are parsed, belong to no test company and back no dev question."""
    return sorted(
        name
        for name, document in documents.items()
        if name in available
        and document.company not in test_companies
        and name not in dev_documents
    )


def letter_share(text: str) -> float:
    """The share of non-space characters that are letters."""
    visible = [character for character in text if not character.isspace()]
    return sum(character.isalpha() for character in visible) / len(visible) if visible else 0.0


def eligible(chunk: Chunk) -> bool:
    return chunk.tokens >= MIN_TOKENS and letter_share(chunk.text) >= MIN_LETTER_SHARE


def sample_chunks(chunks: Sequence[Chunk], per_document: int, seed: int = 0) -> list[Chunk]:
    """Up to `per_document` eligible chunks from each filing, in document order.

    Each filing has its own random stream, so adding a filing leaves the others' samples as
    they were.
    """
    by_document: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_document.setdefault(chunk.doc_name, []).append(chunk)
    picked: list[Chunk] = []
    for name in sorted(by_document):
        pool = sorted(
            (chunk for chunk in by_document[name] if eligible(chunk)),
            key=lambda chunk: chunk.chunk_index,
        )
        rng = random.Random(f"{seed}|{name}")
        sample = rng.sample(pool, min(per_document, len(pool)))
        picked += sorted(sample, key=lambda chunk: chunk.chunk_index)
    return picked


def question_messages(chunk: Chunk) -> list[Message]:
    form = FORMS.get(chunk.doc_type, chunk.doc_type)
    header = f"Company: {chunk.company}\nFiling: {form} for fiscal {chunk.doc_period}"
    return [system(SYSTEM_PROMPT), user(f"{header}\n\nExcerpt:\n{chunk.text}")]


_PREFIX = re.compile(r"^(?:\d+[.)]\s*|[-*]\s*|question\s*[:.]\s*|q\s*[:.]\s*)", re.IGNORECASE)
_SELF_REFERENCE = re.compile(
    r"\b(?:excerpt|passage|the text|this text|the document|this document|this section)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9]+")


def parse_question(text: str) -> str | None:
    """The question from a model reply, or None if it breaks a rule that can be checked."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    question = _PREFIX.sub("", normalise_question(lines[0])).strip().strip("\"'").strip()
    words = len(question.split())
    low, high = QUESTION_WORDS
    if not question.endswith("?") or not low <= words <= high:
        return None
    if _SELF_REFERENCE.search(question):
        return None
    return question


def copies_chunk(question: str, chunk_text: str, length: int = COPIED_WORDS) -> bool:
    """Whether the question repeats `length` or more consecutive words of the chunk."""
    words = _WORD.findall(question.lower())
    text = " " + " ".join(_WORD.findall(chunk_text.lower())) + " "
    return any(
        f" {' '.join(words[i : i + length])} " in text for i in range(len(words) - length + 1)
    )


# Models write typographic quotes, hyphens and spaces; questions use the plain forms.
_TYPOGRAPHY = str.maketrans(
    {
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{LEFT DOUBLE QUOTATION MARK}": '"',
        "\N{RIGHT DOUBLE QUOTATION MARK}": '"',
        "\N{HYPHEN}": "-",
        "\N{NON-BREAKING HYPHEN}": "-",
        "\N{EN DASH}": "-",
        "\N{EM DASH}": "-",
    }
)


def normalise_question(text: str) -> str:
    """NFKC, plain quotes and hyphens, and single spaces."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY).split())


def load_pairs(path: Path) -> list[Pair]:
    """Pairs from a JSON Lines file, with their questions normalised."""
    pairs = []
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if line.strip():
                record = json.loads(line)
                record["question"] = normalise_question(record["question"])
                pairs.append(Pair.model_validate(record))
    return pairs


def summarise(kept_path: Path, rejected_path: Path) -> dict[str, object]:
    """Counts and checksums for a generated set, for its manifest and data card."""
    pairs = load_pairs(kept_path)
    rejected = (
        [
            json.loads(line)
            for line in rejected_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if rejected_path.exists()
        else []
    )
    words = sorted(len(pair.question.split()) for pair in pairs)

    def counts(values: list[str]) -> dict[str, int]:
        return dict(sorted(Counter(values).items()))

    return {
        "pairs": len(pairs),
        "rejected": counts([str(record["reason"]) for record in rejected]),
        "filings": len({pair.doc_name for pair in pairs}),
        "companies": len({pair.company for pair in pairs}),
        "by_model": counts([pair.model for pair in pairs]),
        "by_form": counts([pair.doc_type for pair in pairs]),
        "question_words": {
            "min": words[0] if words else 0,
            "median": words[len(words) // 2] if words else 0,
            "max": words[-1] if words else 0,
        },
        "prompt_version": PROMPT_VERSION,
        "pairs_sha256": hashlib.sha256(kept_path.read_bytes()).hexdigest(),
    }
