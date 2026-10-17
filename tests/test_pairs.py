"""Synthetic pairs: which filings train, which chunks qualify, and what counts as a question."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from copilot.eval.financebench import Document
from copilot.ingest.chunking import Chunk
from copilot.training import pairs


def _document(name: str, company: str) -> Document:
    return Document(
        doc_name=name,
        company=company,
        gics_sector="Industrials",
        doc_type="10k",
        doc_period=2022,
        doc_link="https://example.com",
    )


def _chunk(doc: str, index: int, text: str, tokens: int = 300) -> Chunk:
    return Chunk(
        chunk_id=hashlib.sha256(f"{doc}|{index}".encode()).hexdigest(),
        strategy="tokens-480",
        doc_name=doc,
        chunk_index=index,
        text=text,
        char_start=index * 1000,
        char_end=index * 1000 + len(text),
        pages=(index,),
        section="7",
        company="Acme",
        doc_period=2022,
        doc_type="10k",
        tokens=tokens,
    )


PROSE = "Net sales increased because demand for industrial pumps rose in every region. " * 6


def test_training_documents_leave_out_test_companies_and_dev_filings() -> None:
    documents = {
        name: _document(name, company)
        for name, company in [
            ("ACME_2020_10K", "Acme"),
            ("ACME_2022_10K", "Acme"),
            ("BOLT_2022_10K", "Bolt"),
            ("CRAN_2022_10K", "Crane"),
        ]
    }

    chosen = pairs.training_documents(
        documents,
        test_companies={"Bolt"},
        dev_documents={"ACME_2022_10K"},
        available={"ACME_2020_10K", "ACME_2022_10K", "BOLT_2022_10K"},
    )

    assert chosen == ["ACME_2020_10K"]


def test_only_long_prose_chunks_qualify() -> None:
    table = "2022 2021 2020 1,577 1,612 1,699 (12) 4.5% 3.2% " * 10

    assert pairs.eligible(_chunk("ACME_2020_10K", 0, PROSE))
    assert not pairs.eligible(_chunk("ACME_2020_10K", 1, PROSE, tokens=120))
    assert not pairs.eligible(_chunk("ACME_2020_10K", 2, table))


def test_sampling_is_capped_per_filing_ordered_and_repeatable() -> None:
    chunks = [
        _chunk(doc, i, PROSE) for doc in ("ACME_2020_10K", "ACME_2021_10K") for i in range(10)
    ]

    first = pairs.sample_chunks(chunks, per_document=3, seed=7)
    again = pairs.sample_chunks(list(reversed(chunks)), per_document=3, seed=7)
    alone = pairs.sample_chunks(chunks[:10], per_document=3, seed=7)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in again]
    assert [c.doc_name for c in first].count("ACME_2020_10K") == 3
    assert [c.chunk_index for c in first[:3]] == sorted(c.chunk_index for c in first[:3])
    assert first[:3] == alone


def test_prompts_name_the_company_and_filing() -> None:
    [system_message, user_message] = pairs.question_messages(_chunk("ACME_2020_10K", 0, PROSE))

    assert system_message["role"] == "system"
    assert "Company: Acme" in user_message["content"]
    assert "Form 10-K annual report for fiscal 2022" in user_message["content"]


def test_parse_question_cleans_replies_and_rejects_broken_ones() -> None:
    good = "Why did Acme's net sales of industrial pumps rise in fiscal 2022?"

    assert pairs.parse_question(f'Question: "{good}"') == good
    assert pairs.parse_question(f"1. {good}") == good
    assert pairs.parse_question("What drove sales?") is None  # too short
    assert pairs.parse_question(good.rstrip("?")) is None
    assert pairs.parse_question(f"{good}\nAnother question about Acme's 2022 margins?") is None
    assert (
        pairs.parse_question("What does this excerpt say about Acme's fiscal 2022 sales?") is None
    )


def test_copies_chunk_spots_long_verbatim_runs() -> None:
    copied = "Did net sales increase because demand for industrial pumps rose in every region?"
    fresh = "What lifted Acme's pump revenue across its regions in fiscal 2022?"

    assert pairs.copies_chunk(copied, PROSE)
    assert not pairs.copies_chunk(fresh, PROSE)


def test_questions_are_normalised_when_parsed_and_loaded(tmp_path: Path) -> None:
    fancy = (
        "For 3M\N{RIGHT SINGLE QUOTATION MARK}s fiscal 2015, when did it adopt ASU No."
        "\N{NARROW NO-BREAK SPACE}2015\N{NON-BREAKING HYPHEN}07 and what changed?"
    )
    plain = "For 3M's fiscal 2015, when did it adopt ASU No. 2015-07 and what changed?"
    record = {
        "chunk_id": "c" * 64,
        "doc_name": "3M_2015_10K",
        "company": "3M",
        "doc_period": 2015,
        "doc_type": "10k",
        "question": fancy,
        "model": "test",
    }
    path = tmp_path / "pairs.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert pairs.parse_question(fancy) == plain
    assert [pair.question for pair in pairs.load_pairs(path)] == [plain]


def test_summarise_counts_pairs_and_rejections(tmp_path: Path) -> None:
    def record(doc: str, model: str) -> str:
        return json.dumps(
            {
                "chunk_id": doc.lower() * 4,
                "doc_name": doc,
                "company": doc.split("_")[0],
                "doc_period": 2020,
                "doc_type": "10k",
                "question": "What did the company report about its pump sales in fiscal 2020?",
                "model": model,
            }
        )

    kept, rejected = tmp_path / "pairs.jsonl", tmp_path / "rejected.jsonl"
    kept.write_text(record("ACME_2020_10K", "a") + "\n" + record("BOLT_2020_10K", "b") + "\n")
    rejected.write_text(json.dumps({"chunk_id": "x", "reason": "copied", "reply": "?"}) + "\n")

    summary = pairs.summarise(kept, rejected)

    assert (summary["pairs"], summary["filings"], summary["companies"]) == (2, 2, 2)
    assert summary["rejected"] == {"copied": 1}
    assert summary["by_model"] == {"a": 1, "b": 1}
    assert len(str(summary["pairs_sha256"])) == 64
