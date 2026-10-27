"""The HyDE prompt search's parts: examples by filing, the rank metric and stored vectors."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import HashingDense
from copilot.retrieval.rewrite import HydePrompt, load_hyde_prompt
from copilot.training import hyde
from copilot.training.pairs import Pair

TEXTS = (
    "Net sales rose on higher prices and volumes",
    "Litigation includes product liability claims",
    "Capital expenditures were 1.6 billion dollars",
)


def _chunk(doc: str, index: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=hashlib.sha256(f"{doc}|{index}".encode()).hexdigest(),
        strategy="tokens-480",
        doc_name=doc,
        chunk_index=index,
        text=text,
        char_start=0,
        char_end=len(text),
        pages=(index,),
        section=None,
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        tokens=300,
    )


def _pair(doc: str, number: int) -> Pair:
    return Pair(
        chunk_id=f"{doc}-{number}",
        doc_name=doc,
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        question=f"Question {number} about {doc}?",
        model="test",
    )


def test_split_takes_whole_filings_for_training_and_holds_the_validation_filings_out() -> None:
    pairs = [_pair(f"F{n % 7}", n) for n in range(40)]
    items = hyde.examples(pairs)

    train, val = hyde.split_examples(items, {"F0", "F1"}, size=12)

    assert {item.doc_name for item in val} == {"F0", "F1"}
    assert len(train) == 12
    assert not {item.doc_name for item in train} & {"F0", "F1"}
    assert [item.pair_id for item in items] == list(range(40))


def test_reciprocal_rank_counts_to_ten() -> None:
    assert hyde.reciprocal_rank(0) == 1.0
    assert hyde.reciprocal_rank(3) == 0.25
    assert hyde.reciprocal_rank(10) == 0.0


def test_a_passage_scores_by_where_the_answering_chunk_ranks_in_its_filing() -> None:
    chunks = [_chunk("ACME_2022_10K", n, text) for n, text in enumerate(TEXTS)]
    model = HashingDense()
    index = hyde.ChunkIndex(chunks, model.embed_documents(TEXTS))
    item = hyde.Example(0, "What was Acme's capex?", "ACME_2022_10K", chunks[2].chunk_id)

    assert hyde.passage_score(index, model, item, "Capital expenditures were 1.6 billion") == 1.0
    assert hyde.passage_score(index, model, item, "Net sales rose on higher prices") < 1.0
    assert hyde.passage_score(index, model, item, "   ") == 0.0


def test_filings_are_embedded_once_and_indexed_from_their_files(tmp_path: Path) -> None:
    chunks = {
        "A": [_chunk("A", n, text) for n, text in enumerate(TEXTS[:2])],
        "B": [_chunk("B", 0, TEXTS[2])],
    }
    model = HashingDense()
    seen: list[str] = []

    hyde.embed_filings(chunks, model, tmp_path, log=seen.append)
    hyde.embed_filings(chunks, model, tmp_path, log=seen.append)  # nothing left to do
    index = hyde.build_index(chunks, tmp_path)

    assert len(seen) == 2
    assert index.vectors.shape == (3, model.dim)
    assert np.allclose(index.vectors[2], model.embed_documents([TEXTS[2]])[0])
    with pytest.raises(FileNotFoundError, match="No vectors for 1"):
        hyde.build_index(chunks | {"C": [_chunk("C", 0, "x")]}, tmp_path)


def test_a_written_prompt_loads_back_as_a_hyde_prompt(tmp_path: Path) -> None:
    path = tmp_path / "hyde-2.json"
    prompt = HydePrompt("2", "Write the passage a 10-K would hold.")

    hyde.write_prompt(path, prompt, optimiser="MIPROv2")

    assert load_hyde_prompt(path) == prompt
