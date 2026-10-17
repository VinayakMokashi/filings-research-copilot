# Retrieval baseline

Phase 2, steps 2.4 and 2.5. FinanceBench dev split only; the held-out test split was not opened.

## Question

Which chunking, search mode, reranker and context expansion should the doc agent start from? And does anything beat plain dense search with a statistically significant margin?

## Setup

- **Questions:** the 100 dev questions (20 companies, 58 filings). 77 have one evidence page, 21 have two and 2 have three. Every evidence page is in the question's own filing.
- **Corpus:** the 84 filings behind FinanceBench's open-source questions, parsed with pdfium ([ADR-0009](../decisions/0009-pdf-parsing.md)) and chunked four ways ([chunking](../concepts/chunking.md)). Experiment indexes hold the 58 dev filings; the main index (`tokens-480`) holds all 84.
- **Models:** BAAI/bge-small-en-v1.5 dense vectors (queries prefixed with bge's retrieval instruction); BM25 sparse vectors with Qdrant's IDF; cross-encoders from FastEmbed ([reranking](../concepts/reranking.md)). Qdrant 1.19 ([ADR-0010](../decisions/0010-vector-store-and-embeddings.md)); at this size its dense search is exact ([HNSW check](../concepts/hnsw-and-qdrant.md)).
- **Two settings.** *Oracle document*, the primary one: each question searches only its own filing, which isolates finding the page from finding the filing. *Corpus*: each question searches all 84 filings.
- **Scoring** ([retrieval metrics](../concepts/retrieval-metrics.md)): ranked chunks become ranked pages, each chunk's most-covered page first, and the first 20 distinct pages are scored against the evidence pages: recall@5, 10 and 20, hit@k and MRR@10, each with a 95% bootstrap interval. The decision metric is **recall@10**.
- **Comparisons:** paired permutation tests (10,000 sign flips) against the current baseline, with Holm's adjustment across each family of variants tried, including variants that turned out badly ([ADR-0007](../decisions/0007-evaluation-statistics.md)).
- **One change at a time:** chunking with dense search first, then search mode, reranking and neighbouring chunks on the main index.

## Results

The floor is the first 20 pages of the right filing: recall@10 0.197, hit@20 0.29.

### Search mode

`tokens-480` chunks, bge-small, oracle document:

| Mode | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| **Dense** | **0.485** | **0.608** (0.52 to 0.70) | **0.713** | **0.740** | **0.307** |
| BM25 | 0.325 | 0.425 (0.33 to 0.52) | 0.540 | 0.570 | 0.205 |
| Hybrid, RRF k = 60 | 0.385 | 0.540 (0.45 to 0.64) | 0.645 | 0.680 | 0.289 |
| Hybrid, RRF weights 2 : 1 | 0.405 | 0.470 (0.38 to 0.56) | 0.643 | 0.680 | 0.252 |

Searching all 84 filings (corpus setting):

| Mode | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| **Dense** | **0.170** | **0.345** (0.26 to 0.43) | **0.500** | **0.540** | 0.115 |
| BM25 | 0.090 | 0.155 (0.09 to 0.23) | 0.210 | 0.230 | 0.081 |
| Hybrid, RRF k = 60 | 0.130 | 0.210 (0.14 to 0.29) | 0.355 | 0.390 | **0.126** |

Recall@10 by question type (oracle document):

| Question type | Questions | Dense | BM25 | Hybrid |
|---|---|---|---|---|
| Domain-relevant | 34 | **0.392** | 0.191 | 0.235 |
| Metrics-generated | 33 | **0.742** | 0.333 | 0.636 |
| Novel-generated | 33 | 0.697 | **0.758** | **0.758** |

### Reranking

Dense search's top candidates reordered by a cross-encoder, oracle document:

| Reranker | Candidates | recall@5 | recall@10 (95% interval) | recall@20 | MRR@10 |
|---|---|---|---|---|---|
| None (dense) | | **0.485** | **0.608** (0.52 to 0.70) | 0.713 | **0.307** |
| ms-marco-MiniLM-L-6-v2 | 30 | 0.390 | 0.510 (0.41 to 0.60) | 0.678 | 0.264 |
| jina-reranker-v1-turbo-en | 30 | 0.380 | 0.580 (0.48 to 0.67) | **0.728** | 0.304 |
| bge-reranker-base | 20 | 0.435 | 0.605 (0.52 to 0.70) | 0.703 | 0.284 |

### Neighbouring chunks

Each of the top 5 dense hits followed by the chunk before and after it: recall@10 0.575 (0.48 to 0.67) against 0.608, MRR 0.284 against 0.307.

### Chunking, late chunking and latency

Still running: the `page`, `tokens-256` and `semantic` indexes (dense search against `tokens-480`), the jina-v2-small pair (late chunking against chunk-by-chunk), and latency measured on an otherwise idle machine. They are added here, with the final decision in ADR-0011, when their indexes finish.

## Comparison

Recall@10, paired against dense search on the same chunks, Holm-adjusted within each family:

**Search mode, oracle document** (3 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-oracle` | 0.608 | 0.425 | -0.183 (-0.280 to -0.088) | 0.0004 | 0.0012 | worse |
| `tokens-480_bge-small-hybrid-oracle` | 0.608 | 0.540 | -0.068 (-0.145 to +0.008) | 0.1021 | 0.1021 | no significant difference |
| `tokens-480_bge-small-hybrid-w2-1-oracle` | 0.608 | 0.470 | -0.138 (-0.228 to -0.050) | 0.0040 | 0.0080 | worse |

**Search mode, corpus** (2 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-corpus` | 0.345 | 0.155 | -0.190 (-0.280 to -0.095) | 0.0003 | 0.0006 | worse |
| `tokens-480_bge-small-hybrid-corpus` | 0.345 | 0.210 | -0.135 (-0.225 to -0.045) | 0.0071 | 0.0071 | worse |

**Reranking, oracle document** (3 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-rerank-minilm-l6-oracle` | 0.608 | 0.510 | -0.098 (-0.185 to -0.013) | 0.0326 | 0.0978 | no significant difference |
| `tokens-480_bge-small-dense-rerank-jina-turbo-oracle` | 0.608 | 0.580 | -0.028 (-0.113 to +0.057) | 0.5664 | 1.0000 | no significant difference |
| `tokens-480_bge-small-dense-rerank-bge-base-oracle` | 0.608 | 0.605 | -0.003 (-0.072 to +0.060) | 1.0000 | 1.0000 | no significant difference |

**Neighbouring chunks, oracle document** (1 comparison):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-nb1-oracle` | 0.608 | 0.575 | -0.033 (-0.092 to +0.023) | 0.3128 | 0.3128 | no significant difference |

## Decision

Provisional, until the chunking comparison is in: the doc agent starts from **dense search with bge-small over 480-token chunks**, without BM25 fusion and without a reranker. Nothing tried beat it significantly, and BM25, the 2 : 1 hybrid and the corpus-wide hybrid were significantly worse. Neighbouring chunks stay in the design, but for context building in Phase 3, where answer quality rather than page recall measures them.

## Why nothing beat dense search

Every challenger lost or tied, and the breakdown by question type points at the questions more than at the methods:

- **FinanceBench's templates.** Two thirds of the dev questions are generated from templates that add instructions to the actual question: "Give a response to the question by relying on the details shown in the cash flow statement", "Round your answer to two decimal places", "If operating margin is not a useful metric for a company like this, then state that and explain why". To BM25 those words are as important as "capital expenditure", and they match pages all over every filing. On the human-written *novel* questions, which carry no template, BM25 beats dense search (0.758 against 0.697).
- **Rerankers read the same noise, and less of the chunk.** MS MARCO cross-encoders were trained on short web queries and paragraph-length passages. MiniLM reads at most 512 tokens of question plus chunk, so a 480-token chunk loses its end; jina-turbo reads everything and loses less (0.580 against 0.510). bge-reranker-base, more than ten times MiniLM's size, ties dense search overall (0.605) because its gains and losses cancel: it is better on the human-written questions (0.773 against 0.697) and on metrics questions (0.758 against 0.742), and worse on the templated domain questions (0.294 against 0.392). It also costs a model run per candidate, about 25 seconds a question on the build laptop while it was indexing.
- **The hard questions need reasoning about where to look.** 26 questions have no evidence page in dense search's top 20, 17 of them domain-relevant, such as "Does 3M have a reasonably healthy liquidity profile based on its quick ratio?". The evidence is a balance sheet, and nothing in the question's words says so.
- **Finding the filing is a problem of its own.** Searching all 84 filings instead of the right one drops hit@20 from 0.74 to 0.54.

These point to Phase 3's query understanding (company, period and form as filters) and query rewriting (turning a templated question into what to look for), after which hybrid search and reranking deserve another look.

## Logs

Every run is in `eval/results/retrieval/<run>/dev/` (`summary.md` for reading, `items.jsonl` with each question's retrieved pages), and the comparison tables in `eval/results/retrieval/_comparisons/`. Reproduce a run with `uv run poe run-retrieval` and the options in its `summary.json`.
