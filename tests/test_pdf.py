"""PDF parsing: text normalisation, boilerplate removal and section tagging."""

from __future__ import annotations

from pathlib import Path

import pytest

from copilot.ingest import pdf
from copilot.ingest.pdf import Page

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = ROOT / "data" / "raw" / "financebench" / "pdfs" / "3M_2018_10K.pdf"


def _unique(n: int) -> str:
    """A sentence that differs on every page, even after digits are masked."""
    word = "".join(chr(ord("a") + int(digit)) for digit in str(n))
    return f"This page discusses {word} topics."


def test_normalise_text_fixes_ligatures_hyphens_and_line_ends() -> None:
    raw = f"Of{chr(0xFB01)}ce\r\nnet{chr(0xAD)}work\rend"

    assert pdf.normalise_text(raw) == "Office\nnetwork\nend"


def test_running_headers_and_page_numbers_are_removed() -> None:
    pages = [
        f"Table of Contents\n{_unique(n)}\nAlso {_unique(n + 100)}\n{n + 1}" for n in range(20)
    ]

    shapes = pdf.boilerplate_shapes(pages)

    assert shapes == {"table of contents", "#"}
    assert pdf.strip_boilerplate(pages[4], shapes) == f"{_unique(4)}\nAlso {_unique(104)}"


def test_headings_units_and_table_rows_are_never_boilerplate() -> None:
    kept = [
        "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS",
        "(Dollars in millions)",
        "Revenue 1,234 5,678 9,012",
    ]
    pages = [f"{line}\n{_unique(n)}" for n, line in enumerate(kept * 10)]

    assert pdf.boilerplate_shapes(pages) == set()


def test_form_numbers_dont_count_as_table_figures() -> None:
    pages = [f"{_unique(n)}\n2019 FORM 10-K {n + 1}" for n in range(20)]

    assert pdf.boilerplate_shapes(pages) == {"# form #-k #"}


def test_short_documents_keep_titles_repeated_on_a_few_pages() -> None:
    pages = [f"Reconciliation of non-GAAP measures\n{_unique(n)}" for n in range(3)]
    pages += [_unique(n) for n in range(10, 17)]

    assert pdf.boilerplate_shapes(pages) == set()


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Item 7. Management's Discussion and Analysis", ("7", False)),
        ("ITEM 1A RISK FACTORS", ("1A", False)),
        ("Item 7A.", ("7A", False)),
        ("Item 2.02 Results of Operations and Financial Condition", ("2.02", False)),
        ("ITEM 1 Business 4", ("1", True)),
        ("Item 8 of this report contains the statements", None),
        ("Itemized deductions", None),
    ],
)
def test_heading_recognition(line: str, expected: tuple[str, bool] | None) -> None:
    assert pdf._heading(line) == expected


def test_sections_run_from_heading_to_heading_and_skip_contents_pages() -> None:
    pages = [
        "Table of Contents\nItem 1. Business 3\nItem 1A. Risk Factors 10\nItem 7. MD&A 24",
        "PART I\nItem 1. Business\nWe make things.",
        "More about the business.",
        "Item 1A. Risk Factors\nThings could go wrong.",
        "Item 7 of this report explains results.\nStill risk factors.",
        "Item 7. Management's Discussion and Analysis\nResults improved.",
    ]

    tagged = pdf.tag_sections(pages, "10k")

    assert [start for start, _ in tagged] == [None, None, "1", "1", "1A", "1A"]
    assert tagged[1][1] == ((7, "1"),)
    assert tagged[4][1] == ()


def test_ten_q_sections_include_the_part() -> None:
    pages = [
        "PART I. FINANCIAL INFORMATION\nItem 2. Management's Discussion and Analysis",
        "PART II. OTHER INFORMATION\nItem 1A. Risk Factors",
    ]

    tagged = pdf.tag_sections(pages, "10q")

    assert [label for _, headings in tagged for _, label in headings] == ["I-2", "II-1A"]


def test_section_at_follows_headings_within_a_page() -> None:
    page = Page("DOC", 3, "end of 1A\nItem 2. Properties\nwe own buildings", "1A", ((10, "2"),))

    assert page.section_at(0) == "1A"
    assert page.section_at(9) == "1A"
    assert page.section_at(10) == "2"
    assert page.section_at(40) == "2"


def test_pages_round_trip_through_jsonl(tmp_path: Path) -> None:
    pages = [
        Page("DOC", 0, "Cover", None, ()),
        Page("DOC", 1, "Item 1. Business", None, ((0, "1"),)),
    ]
    path = tmp_path / "DOC.jsonl"

    pdf.write_pages(pages, path)

    assert pdf.read_pages(path) == pages


@pytest.mark.integration
@pytest.mark.skipif(
    not SAMPLE_PDF.exists(), reason="needs FinanceBench PDFs (poe fetch-financebench)"
)
def test_a_real_filing_parses_with_sections() -> None:
    pages = pdf.parse_document(SAMPLE_PDF, "3M_2018_10K", "10k")

    assert len(pages) == 160
    assert "Cash Flows" in pages[59].text
    assert pages[59].section_at(0) == "8"
    assert not pages[59].text.lower().startswith("table of contents")
