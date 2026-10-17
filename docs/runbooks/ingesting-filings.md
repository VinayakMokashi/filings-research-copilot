# Ingesting filings

How to turn the FinanceBench PDFs into searchable chunks. This runbook grows with Phase 2: parsing comes first, then chunking and indexing.

## Before you start

```bash
uv run poe fetch-financebench               # the PDFs the questions use (84 files, 159 MB)
uv run poe fetch-financebench --pdfs all    # every PDF in the corpus (368 files, 706 MB)
```

## Parse

```bash
uv run poe parse-pdfs
```

Each PDF becomes `data/processed/pages/<doc_name>.jsonl`: one line per page with its 0-based page number, clean text, the section it starts in, and any section headings on it ([ADR-0009](../decisions/0009-pdf-parsing.md)). The 84 question documents take about 25 seconds with 8 worker processes; change that with `--workers`.

A rerun parses only PDFs that are new or have changed. Changing the parser's output means bumping `PARSER_VERSION` in `src/copilot/ingest/pdf.py`, which reparses everything on the next run.

## Check the pages

```bash
uv run poe check-pages
```

This compares FinanceBench's text for every dev evidence page with the parsed page of the same index and with its neighbours. It writes `eval/results/parsing/page-alignment-dev.md`. Expect 126 of 127 to line up; a sudden drop means page numbering or text extraction has broken.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| A document has no section tags | Its PDF has no entry in FinanceBench's document file (7 of the 368 don't), or it is an earnings release, which has no items. Nothing to fix. |
| A page has no text | The page is an image. pdfium can't read text from images, and the corpus has 82 such pages. |
| `BrokenProcessPool` | A worker crashed, usually on a damaged PDF. Run `poe fetch-financebench` to re-verify the files, then parse again; finished documents are kept. |
