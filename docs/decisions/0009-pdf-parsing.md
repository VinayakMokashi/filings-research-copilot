# ADR-0009: Parse filings with pdfium, page by page

- **Status:** Accepted
- **Date:** 2026-10-17
- **Phase:** 2

## Context

Retrieval is scored, and answers are cited, by page: FinanceBench gives each evidence passage as a 0-based PDF page index. The parser therefore has to produce page-accurate text for 368 filings (12,013 pages in the 84 the questions use), on a laptop CPU, under a licence compatible with this MIT repository. 39 of the 84 PDFs are AES-encrypted (owner-password protected, readable without a password).

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **pypdfium2 (pdfium)** | 85 to 100 pages a second on one core; Apache and BSD licences; opens the encrypted PDFs; its text matches FinanceBench's evidence pages | Plain text only: tables lose their columns |
| pypdf | Pure Python, BSD licence | About 10 times slower (9 pages a second); needs the `cryptography` package for the encrypted PDFs; lower agreement with FinanceBench's pages |
| PyMuPDF | Fast, good layout handling | AGPL licence |
| pdfplumber (pdfminer.six) | Can extract tables | Slow on long filings |
| Docling or unstructured | Layout and table models | Large ML models, slow on a CPU, heavy dependencies |

## Decision

Parse with pypdfium2, one page at a time, numbering pages from 0. Normalise the text (NFKC, Unix line ends, no soft hyphens), remove running headers and footers, and tag each page with the section it is in, using the rules documented in `copilot.ingest.pdf`. Cache each document's pages as JSON Lines, with a manifest of the parser version and each PDF's git blob id, so only new or changed documents are parsed again.

Table-aware parsing is deferred. Reported numbers come from XBRL facts (ADR-0008), so the doc agent mainly needs narrative text; Phase 3's error analysis will show whether flattened tables cost answers.

## Evidence

- **Benchmark** on 10 documents with dev evidence (1,340 pages, one process): pypdfium2 parsed 85 to 101 pages a second, pypdf 9. On the 23 evidence pages, median word overlap with FinanceBench's page text was 1.000 for pypdfium2 (minimum 0.98) and 0.987 for pypdf (minimum 0.89).
- **Alignment** over every dev evidence passage: 126 of 127 match the parsed page of the same index, with a median word overlap of 0.99. The remaining one (CVS Health 2018, page 303) is still the closest page, with 0.47 overlap ([report](../../eval/results/parsing/page-alignment-dev.md)).
- **Throughput:** the 84 documents parse in 25 seconds with 8 processes. 82 pages carry no text: they are images.
- **Header and footer rule**, tuned on the corpus: a line repeated at the page edges must appear on at least 10% of pages, and on at least 5. The share copes with PepsiCo's 549-page 2021 10-K, where "Table of Contents" heads under a quarter of the pages; the floor of 5 keeps table titles repeated on 3 pages of a 27-page 8-K. Item and part headings, unit lines and lines with more than two numbers are never removed, which protects Microsoft's running item headers and the table rows of Johnson & Johnson's 8-K.

## Consequences

- Tables arrive as lines of text with their columns run together; numeric questions go to the SQL agent.
- Image-only pages have no text; OCR is out of scope unless evidence turns up on them.
- Section tags let later phases filter or boost by part of the filing, such as Item 1A for risk questions.
- Any change to parsing output bumps `PARSER_VERSION`, which reparses every document on the next run.

## References

- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), Python bindings to Google's PDFium.
- SEC, Form 10-K and Form 10-Q general instructions (the item structure).
