# Ingesting filings

How to turn the FinanceBench PDFs into searchable chunks. This runbook grows with Phase 2: parsing and chunking so far, indexing next.

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

## Chunk

```bash
uv run poe chunk-corpus --strategy tokens-480    # or page, tokens-256
```

Each strategy writes `data/processed/chunks/<strategy>/<doc_name>.jsonl` and a `_summary.json`. Chunks are measured in the embedding model's own tokens (BAAI/bge-small-en-v1.5, downloaded on first use), so none is cut off by its 512-token limit. On the 84 question documents:

| Strategy | Chunks | Median tokens | Chunks crossing a page | Time |
|---|---|---|---|---|
| `page` | 23,585 | 448 | 0% | 20 s |
| `tokens-480` (64 overlap) | 21,899 | 462 | 52% | 40 s |
| `tokens-256` (32 overlap) | 39,573 | 242 | 30% | 42 s |

Rerunning a strategy rewrites its files. The semantic and late-chunking strategies need an embedding model and run as part of indexing.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| A document has no section tags | Its PDF has no entry in FinanceBench's document file (7 of the 368 don't), or it is an earnings release, which has no items. Nothing to fix. |
| A page has no text | The page is an image. pdfium can't read text from images, and the corpus has 82 such pages. |
| `BrokenProcessPool` | A worker crashed, usually on a damaged PDF. Run `poe fetch-financebench` to re-verify the files, then parse again; finished documents are kept. |
