"""Parsing the corpus resumably: the manifest, skipping and reparsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from copilot.eval.financebench import Document
from copilot.ingest import corpus
from copilot.ingest.pdf import Page


@pytest.fixture
def parsed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the PDF parser with a fake that records which documents it parsed."""
    calls: list[str] = []

    def fake_parse(path: Path, doc_name: str, doc_type: str) -> list[Page]:
        calls.append(doc_name)
        return [
            Page(doc_name, 0, "Cover page of the Acme annual report", None, ()),
            Page(doc_name, 1, "", None, ()),
        ]

    monkeypatch.setattr(corpus, "parse_document", fake_parse)
    return calls


def _documents() -> dict[str, Document]:
    return {
        name: Document(
            doc_name=name,
            company="Acme",
            gics_sector="Industrials",
            doc_type="10k",
            doc_period=2022,
            doc_link="https://example.com",
        )
        for name in ("ACME_2022_10K", "ACME_2023_10K")
    }


def test_parse_corpus_parses_once_and_resumes(tmp_path: Path, parsed: list[str]) -> None:
    pdf_dir, out_dir = tmp_path / "pdfs", tmp_path / "pages"
    pdf_dir.mkdir()
    for name in _documents():
        (pdf_dir / f"{name}.pdf").write_bytes(f"%PDF {name}".encode())

    first = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)
    again = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)

    assert (first.parsed, first.skipped, again.parsed, again.skipped) == (2, 0, 0, 2)
    assert parsed == ["ACME_2022_10K", "ACME_2023_10K"]
    entry = again.manifest.docs["ACME_2022_10K"]
    assert (entry.pages, entry.empty_pages, entry.doc_type) == (2, 1, "10k")
    assert corpus.page_text(out_dir, "ACME_2023_10K") == [
        "Cover page of the Acme annual report",
        "",
    ]


def test_a_changed_pdf_or_parser_is_parsed_again(
    tmp_path: Path, parsed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_dir, out_dir = tmp_path / "pdfs", tmp_path / "pages"
    pdf_dir.mkdir()
    for name in _documents():
        (pdf_dir / f"{name}.pdf").write_bytes(f"%PDF {name}".encode())
    corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)

    (pdf_dir / "ACME_2023_10K.pdf").write_bytes(b"%PDF changed")
    changed = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)
    monkeypatch.setattr(corpus, "PARSER_VERSION", "next")
    upgraded = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)

    assert changed.parsed == 1
    assert upgraded.parsed == 2
    assert upgraded.manifest.parser_version == "next"


def test_summary_counts_ten_k_sections(tmp_path: Path, parsed: list[str]) -> None:
    pdf_dir, out_dir = tmp_path / "pdfs", tmp_path / "pages"
    pdf_dir.mkdir()
    (pdf_dir / "ACME_2022_10K.pdf").write_bytes(b"%PDF")

    report = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)

    assert corpus.manifest_summary(report.manifest) == {
        "documents": 1,
        "pages": 2,
        "empty_pages": 1,
        "ten_k_pages": 2,
        "ten_k_sectioned_pages": 0,
    }


def test_a_pdf_that_fails_is_reported_and_the_rest_are_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_parse(path: Path, doc_name: str, doc_type: str) -> list[Page]:
        if doc_name == "ACME_2022_10K":
            raise ValueError("Data format error")
        return [Page(doc_name, 0, "Cover page of the Acme annual report", None, ())]

    monkeypatch.setattr(corpus, "parse_document", fake_parse)
    pdf_dir, out_dir = tmp_path / "pdfs", tmp_path / "pages"
    pdf_dir.mkdir()
    for name in _documents():
        (pdf_dir / f"{name}.pdf").write_bytes(f"%PDF {name}".encode())

    report = corpus.parse_corpus(pdf_dir, out_dir, _documents(), workers=1)

    assert report.failed == {"ACME_2022_10K": "ValueError: Data format error"}
    assert (report.parsed, list(report.manifest.docs)) == (1, ["ACME_2023_10K"])
