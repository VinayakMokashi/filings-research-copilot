# Ingesting filings

How to turn the FinanceBench PDFs into searchable chunks: parse, chunk, then index into Qdrant.

## Before you start

```bash
uv run poe fetch-financebench               # the PDFs the questions use (84 files, 159 MB)
uv run poe fetch-financebench --pdfs all    # every PDF in the corpus (368 files, 706 MB)
```

## Parse

```bash
uv run poe parse-pdfs
```

Each PDF becomes `data/processed/pages/<doc_name>.jsonl`: one line per page with its 0-based page number, clean text, the section it starts in, and any section headings on it ([ADR-0009](../decisions/0009-pdf-parsing.md)). The 84 question documents take about 25 seconds with 8 worker processes (change that with `--workers`); all 368 give 366 documents and 53,901 pages.

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

Rerunning a strategy rewrites its files. The semantic strategy needs the embedding model, so `poe index-corpus --strategy semantic` chunks and caches it; late chunking changes only the vectors, not the chunks.

## Index

```bash
uv run poe services-up                                                          # Qdrant on 127.0.0.1:6333
uv run poe index-corpus --strategy page --model bge-small --docs all            # the baseline index (ADR-0011)
uv run poe index-corpus --strategy tokens-480 --docs dev                        # an experiment, dev documents only
uv run poe index-corpus --strategy tokens-480 --model jina-small --late --docs dev
```

Each run fills the collection `fb_<strategy>_<model>` with one point per chunk: a bge-small dense vector, a BM25 sparse vector and the chunk as payload ([ADR-0010](../decisions/0010-vector-store-and-embeddings.md)). It reads the chunk files from `poe chunk-corpus` when they exist, and otherwise chunks the document and caches the result (`--rechunk` ignores the cache). `--docs dev` takes the 58 documents behind dev questions; `--docs all` adds the other 26 behind FinanceBench's questions after them, so dev evaluation can start before the run ends; `--docs corpus` takes every parsed filing (366), for a product index rather than evaluation. `--limit N` indexes only the first N documents, for a quick check.

It writes, under `data/processed/indexes/`:

- `<collection>.log.jsonl`: one line per document with its chunk count, how many were added, seconds taken and any error;
- `<collection>.json`: the index card, with the models, query prefix, vector and HNSW settings, payload indexes and counts.

Indexing is CPU-bound: about 8 chunks a second for 480-token chunks on an 8-core laptop, so an 84-filing index takes 45 to 80 minutes and a dev-only experiment 20 to 90 minutes. **An interrupted run resumes**: run the same command again and it embeds only the chunks the collection doesn't hold yet.

Useful while it runs:

```bash
tail -f data/processed/indexes/fb_tokens-480_bge-small.log.jsonl
curl -s http://127.0.0.1:6333/collections/fb_tokens-480_bge-small   # points_count, status
```

The Qdrant dashboard is at <http://127.0.0.1:6333/dashboard>. To rebuild a collection from scratch, delete it first: `curl -X DELETE http://127.0.0.1:6333/collections/<name>`.

`uv run poe check-hnsw` copies the main index into a scratch collection that builds an HNSW graph in every segment, and reports recall@10 and latency against exact search for the dev questions (`eval/results/indexing/`).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| A document has no section tags | Its PDF has no entry in FinanceBench's document file (7 of the 368 don't), or it is an earnings release, which has no items. Nothing to fix. |
| A page has no text | The page is an image. pdfium can't read text from images, and the corpus has 82 such pages. |
| `could not parse <document>` | The PDF can't be opened. Two FinanceBench PDFs, Intel's 8-Ks of 2023-02-10 and 2023-08-16, are truncated in the source repository itself, so this is expected for them; the run parses everything else and exits with status 1. For any other file, run `poe fetch-financebench` to re-verify it. |
| `BrokenProcessPool` | A worker process crashed outright. Run `poe fetch-financebench` to re-verify the files, then parse again; finished documents are kept. |
| `Connection refused` on port 6333 | Qdrant isn't running: `uv run poe services-up`. |
| Indexing is much slower than 8 chunks a second | Another CPU-heavy job is running (only one indexing run at a time helps), or Windows is on a power-saving plan. Texts are embedded one at a time on purpose: batches were slower on this CPU. |
| A model download fails | Hugging Face rate-limits anonymous downloads. Run the command again; models are cached in `data/models` (FastEmbed) and `~/.cache/huggingface` (jina). |
