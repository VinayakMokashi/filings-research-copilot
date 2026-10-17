"""Parse filing PDFs into clean page text, tagged with the section each page is in (ADR-0009).

Pages are numbered from 0, the way FinanceBench numbers its evidence pages. Three steps:

1. **Extract** each page's text with pdfium, normalised (NFKC, so ligatures become letters;
   Unix line ends; no soft hyphens).
2. **Strip running headers and footers.** A line counts as boilerplate when, after lower-casing
   and replacing digits with `#`, it appears among the first or last two lines of at least 10%
   of the document's pages, and of at least 5 pages: "Table of Contents" links, page numbers,
   company names. Item and part headings, unit lines ("in millions") and lines with more than
   two numbers (table rows) are always kept. A share of the pages, rather than a count, copes
   with long exhibits (PepsiCo's 2021 10-K has 549 pages, a quarter of them headed "Table of
   Contents"); the five-page floor keeps repeated table titles in short 8-Ks.
3. **Tag sections.** A heading line such as "Item 7. Management's Discussion and Analysis"
   starts a section that runs until the next heading. 10-K sections are item codes (`7`,
   `1A`), 10-Q sections add the part (`I-2`), and 8-K items keep their decimals (`2.02`).
   Tables of contents are ignored (pages with two or more item lines ending in a page number,
   or four or more item headings), and so are lines that continue a sentence ("Item 8 of
   this report ...").
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

PARSER_VERSION = "2"  # bump when parsing output changes, so cached pages are rebuilt

EDGE_LINES = 2
BOILERPLATE_SHARE = 0.10
BOILERPLATE_MIN_PAGES = 5
MAX_BOILERPLATE_NUMBERS = 2
TOC_MIN_HEADINGS = 4
TOC_MIN_NUMBERED_ENTRIES = 2
MAX_HEADING_CHARS = 150
SECTIONED_TYPES = frozenset({"10k", "10q", "8k"})

_DASHES = "\N{EN DASH}\N{EM DASH}"
_ITEM = re.compile(
    r"^\s*item\s+(\d{1,2}(?:\.\d{2})?[a-c]?)(?!\w)(?!\.\d)\s*[.:" + _DASHES + r"-]?\s*(.*)$",
    re.IGNORECASE,
)
_PART = re.compile(r"^\s*part\s+(iv|i{1,3})(?![a-z])", re.IGNORECASE)
_TRAILING_PAGE_NUMBER = re.compile(r"\s\d{1,3}\s*$")
_UNITS = re.compile(r"\bin (?:thousands|millions|billions)\b", re.IGNORECASE)
_REMOVED_CHARACTERS = str.maketrans({"\N{SOFT HYPHEN}": None, "\x02": None, "\x00": None})

TEN_K_ITEMS: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for the Registrant's Common Equity",
    "6": "Selected Financial Data (reserved since 2021)",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements with Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}

Headings = tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class Page:
    """One page: clean text, the section it starts in, and the headings found on it."""

    doc_name: str
    page: int
    text: str
    section: str | None
    headings: Headings

    def section_at(self, offset: int) -> str | None:
        """The section in force at a character offset of this page's text."""
        section = self.section
        for start, heading in self.headings:
            if start > offset:
                break
            section = heading
        return section


def extract_pages(path: Path) -> list[str]:
    """The normalised text of every page, in order."""
    pdf = pdfium.PdfDocument(path)
    try:
        texts = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            texts.append(normalise_text(textpage.get_text_bounded()))
            textpage.close()
            page.close()
        return texts
    finally:
        pdf.close()


def normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_REMOVED_CHARACTERS)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _shape(line: str) -> str:
    """A line's identity for boilerplate detection: lower case, digits as '#', single spaces."""
    return " ".join(re.sub(r"\d+", "#", line.lower()).split())


def _content_lines(text: str) -> list[str]:
    return [line for line in text.split("\n") if line.strip()]


def _may_be_boilerplate(line: str) -> bool:
    """Section headings, table rows and unit lines are never treated as boilerplate."""
    if _ITEM.match(line) or _PART.match(line) or _UNITS.search(line):
        return False
    # The "10" in "Form 10-K" isn't a table figure, so footers such as "2019 FORM 10-K 45" qualify.
    numbers = _shape(line).replace("#-k", "k").replace("#-q", "q").count("#")
    return numbers <= MAX_BOILERPLATE_NUMBERS


def boilerplate_shapes(pages: Sequence[str]) -> set[str]:
    """Line shapes that recur at the top or bottom of many pages (see the module docstring)."""
    counts: Counter[str] = Counter()
    for text in pages:
        lines = _content_lines(text)
        edges = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
        counts.update({_shape(line) for line in edges if _may_be_boilerplate(line)})
    threshold = max(BOILERPLATE_MIN_PAGES, BOILERPLATE_SHARE * len(pages))
    return {shape for shape, n in counts.items() if n >= threshold and shape}


def strip_boilerplate(text: str, shapes: set[str]) -> str:
    """Drop boilerplate lines from the top and bottom edges of one page."""
    lines = _content_lines(text)
    edge = set(range(EDGE_LINES)) | set(range(len(lines) - EDGE_LINES, len(lines)))
    kept = [line for i, line in enumerate(lines) if not (i in edge and _shape(line) in shapes)]
    return "\n".join(kept)


def _heading(line: str) -> tuple[str, bool] | None:
    """The item code, and whether the line is a table-of-contents entry, or None."""
    if len(line.strip()) > MAX_HEADING_CHARS:
        return None
    match = _ITEM.match(line)
    if match is None:
        return None
    code, title = match.group(1).upper(), match.group(2).strip()
    if title and not (title[0].isupper() or title[0].isdigit() or title[0] in "(\"'"):
        return None  # a sentence that happens to start with "Item 8 of this report"
    # A trailing page number marks a table-of-contents entry, such as "Item 7. MD&A 24".
    return code, bool(_TRAILING_PAGE_NUMBER.search(line))


def tag_sections(pages: Sequence[str], doc_type: str) -> list[tuple[str | None, Headings]]:
    """For each page: the section it starts in, and the (offset, section) of its headings."""
    tagged: list[tuple[str | None, Headings]] = []
    section: str | None = None
    part: str | None = None
    for text in pages:
        start_section = section
        found: list[tuple[int, str]] = []
        numbered_entries = 0
        offset = 0
        for line in text.split("\n"):
            part_match = _PART.match(line)
            if part_match is not None and len(line.strip()) <= MAX_HEADING_CHARS:
                part = part_match.group(1).upper()
            heading = _heading(line)
            if heading is not None:
                code, is_toc_entry = heading
                if is_toc_entry:
                    numbered_entries += 1
                else:
                    found.append((offset, f"{part}-{code}" if doc_type == "10q" and part else code))
            offset += len(line) + 1
        if len(found) >= TOC_MIN_HEADINGS or numbered_entries >= TOC_MIN_NUMBERED_ENTRIES:
            found = []  # a table of contents, not section starts
        if found:
            section = found[-1][1]
        tagged.append((start_section, tuple(found)))
    return tagged


def parse_document(path: Path, doc_name: str, doc_type: str) -> list[Page]:
    raw = extract_pages(path)
    shapes = boilerplate_shapes(raw)
    clean = [strip_boilerplate(text, shapes) for text in raw]
    sections: list[tuple[str | None, Headings]]
    if doc_type in SECTIONED_TYPES:
        sections = tag_sections(clean, doc_type)
    else:
        sections = [(None, ())] * len(clean)
    return [
        Page(doc_name, index, text, start, headings)
        for index, (text, (start, headings)) in enumerate(zip(clean, sections, strict=True))
    ]


def write_pages(pages: Sequence[Page], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for page in pages:
            record = {
                "doc_name": page.doc_name,
                "page": page.page,
                "section": page.section,
                "headings": [list(h) for h in page.headings],
                "text": page.text,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_pages(path: Path) -> list[Page]:
    with path.open(encoding="utf-8") as lines:
        records = [json.loads(line) for line in lines if line.strip()]
    return [
        Page(
            r["doc_name"],
            r["page"],
            r["text"],
            r["section"],
            tuple((int(offset), str(label)) for offset, label in r["headings"]),
        )
        for r in records
    ]
