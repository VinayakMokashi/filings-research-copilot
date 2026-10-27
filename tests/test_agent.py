"""The doc agent end to end, on an in-memory index with fake models."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient

from copilot.answer.agent import DocAgent
from copilot.answer.bandit import ArmChooser
from copilot.ingest import index
from copilot.ingest.chunking import Chunk
from copilot.ingest.embed import HashingDense, HashingSparse
from copilot.llm import FakeLLM, Message, ModelRole
from copilot.retrieval.query import CompanyMatcher, Filing
from copilot.retrieval.rewrite import Search
from copilot.retrieval.search import Searcher

SPEC = index.IndexSpec("page", "hashing", 64)
PAGES = {
    ("ACME_2022_10K", 0): "Acme net revenue for fiscal 2022 was 1,200 million dollars.",
    ("ACME_2022_10K", 1): "Acme employees and properties in fiscal 2022.",
    ("ACME_2021_10K", 0): "Acme net revenue for fiscal 2021 was 1,000 million dollars.",
}
FILINGS = [
    Filing("ACME_2021_10K", "Acme", "10k", 2021),
    Filing("ACME_2022_10K", "Acme", "10k", 2022),
]


def _searcher() -> Searcher:
    client = QdrantClient(":memory:")
    index.ensure_collection(client, SPEC)
    chunks = [
        Chunk(
            chunk_id=hashlib.sha256(f"{doc}|{page}".encode()).hexdigest(),
            strategy="page",
            doc_name=doc,
            chunk_index=page,
            text=text,
            char_start=0,
            char_end=len(text),
            pages=(page,),
            section="7",
            company="Acme",
            doc_period=int(doc.split("_")[1]),
            doc_type="10k",
            tokens=len(text.split()),
        )
        for (doc, page), text in PAGES.items()
    ]

    def embed(batch: Sequence[Chunk]) -> NDArray[np.float32]:
        return HashingDense().embed_documents([chunk.text for chunk in batch])

    index.index_chunks(client, SPEC.collection, chunks, embed, HashingSparse())
    return Searcher(client, SPEC.collection, HashingDense(), HashingSparse())


def _replies(answers: list[dict[str, object]]) -> FakeLLM:
    queue = list(answers)

    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        if role == "strong":
            return json.dumps(queue.pop(0))
        task = messages[-1]["content"]
        return (
            "Acme net revenue fiscal 2022" if "Write the passage" not in task else "Revenue rose."
        )

    return FakeLLM(reply)


def _agent(llm: FakeLLM) -> DocAgent:
    return DocAgent(_searcher(), CompanyMatcher(["Acme"], {"Acme": None}), FILINGS, llm)


def test_the_agent_answers_from_the_resolved_filing() -> None:
    llm = _replies(
        [{"answerable": True, "answer": "Revenue was $1,200 million [1].", "calculations": []}]
    )

    result = _agent(llm).answer("What was Acme's FY2022 revenue?")

    assert result.retrieval.filings == ["ACME_2022_10K"]
    assert {source.doc_name for source in result.answer.sources} == {"ACME_2022_10K"}
    assert result.answer.answerable
    assert result.answer.cited == [1]
    assert not result.retried


def test_an_empty_answer_retries_across_the_company_filings() -> None:
    llm = _replies(
        [
            {"answerable": False, "answer": "", "missing": "the 2021 figure"},
            {"answerable": True, "answer": "Revenue grew [1][2].", "calculations": []},
        ]
    )

    result = _agent(llm).answer("Did Acme's revenue grow in FY2022?")

    assert result.retried
    assert result.first is not None
    assert not result.first.answerable
    assert result.retrieval.filings == ["ACME_2021_10K", "ACME_2022_10K"]
    assert result.retrieval.searches[-1].text == "the 2021 figure"
    assert result.retrieval.searches[-1].source == "missing"
    assert result.answer.answerable
    assert sum(call.role == "strong" for call in llm.calls) == 2


def test_a_single_filing_is_searched_again_for_what_was_missing() -> None:
    llm = _replies(
        [
            {"answerable": False, "answer": "", "missing": "employees in fiscal 2022"},
            {"answerable": True, "answer": "It had 500 employees [1].", "calculations": []},
        ]
    )
    agent = DocAgent(_searcher(), CompanyMatcher(["Acme"], {"Acme": None}), FILINGS[1:], llm)

    result = agent.answer("How many people did Acme employ in FY2022?")

    assert result.retried
    assert result.retrieval.filings == ["ACME_2022_10K"]
    assert result.retrieval.searches[-1] == Search("employees in fiscal 2022", source="missing")
    assert agent.retry_budget == 4500
    assert result.answer.answerable
    assert sum(call.role == "strong" for call in llm.calls) == 2


def test_a_refusal_with_nothing_to_widen_or_search_is_final() -> None:
    llm = _replies([{"answerable": False, "answer": "", "missing": ""}])
    agent = DocAgent(_searcher(), CompanyMatcher(["Acme"], {"Acme": None}), FILINGS[1:], llm)

    result = agent.answer("How many people did Acme employ in FY2022?")

    assert not result.retried
    assert sum(call.role == "strong" for call in llm.calls) == 1


def test_a_bandit_chooses_the_answer_model_and_the_answer_names_its_arm(tmp_path: Path) -> None:
    llm = _replies(
        [{"answerable": True, "answer": "Revenue was $1,200 million [1].", "calculations": []}]
    )
    arms = ArmChooser(tmp_path / "arms.json", arms=("strong-low",))
    agent = DocAgent(_searcher(), CompanyMatcher(["Acme"], {"Acme": None}), FILINGS, llm, arms=arms)

    result = agent.answer("What was Acme's FY2022 revenue?")

    answer_calls = [call for call in llm.calls if call.role == "strong"]
    assert answer_calls[0].extra.get("reasoning_effort") == "low"
    assert result.arm == "strong-low"
    assert (
        _agent(_replies([{"answerable": True, "answer": "x [1].", "calculations": []}]))
        .answer("What was Acme's FY2022 revenue?")
        .arm
        is None
    )
