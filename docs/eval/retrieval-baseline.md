# Retrieval baseline

Phase 2, steps 2.4 to 2.6. FinanceBench dev split only; the held-out test split was not opened.

> **Corrected on 2026-10-18.** The first version of this report gave BM25 and hybrid numbers from runs made while the main index was still being built (BM25's IDF depends on the whole collection) and from Qdrant's server-side fusion, which returned tied results in a different order on each call. Every number here comes from complete 84-filing indexes, with fusion done in our own code, which repeats exactly. BM25's recall@10 moved from 0.425 to 0.440; no conclusion changed.

## Question

Which chunking, search mode, reranker and context expansion should the doc agent start from? And does anything beat plain dense search with a statistically significant margin?

## Setup

- **Questions:** the 100 dev questions (20 companies, 58 filings). 77 have one evidence page, 21 have two and 2 have three. Every evidence page is in the question's own filing.
- **Corpus:** the 84 filings behind FinanceBench's open-source questions, parsed with pdfium ([ADR-0009](../decisions/0009-pdf-parsing.md)) and chunked four ways ([chunking](../concepts/chunking.md)). The `tokens-480` and `page` indexes hold all 84 filings; the other experiment indexes hold the 58 dev filings, which is all the oracle-document setting needs.
- **Models:** BAAI/bge-small-en-v1.5 dense vectors (queries prefixed with bge's retrieval instruction); BM25 sparse vectors with Qdrant's IDF; cross-encoders from FastEmbed ([reranking](../concepts/reranking.md)). Qdrant 1.19 ([ADR-0010](../decisions/0010-vector-store-and-embeddings.md)); at this size its dense search is exact ([HNSW check](../concepts/hnsw-and-qdrant.md)). Hybrid search fuses the dense and BM25 rankings in our own code with reciprocal rank fusion (k = 60), after putting each ranking in a fixed order ([hybrid search](../concepts/hybrid-search-and-rrf.md)).
- **Two settings.** *Oracle document*, the primary one: each question searches only its own filing, which isolates finding the page from finding the filing. *Corpus*: each question searches all 84 filings.
- **Scoring** ([retrieval metrics](../concepts/retrieval-metrics.md)): ranked chunks become ranked pages, each chunk's most-covered page first, and the first 20 distinct pages are scored against the evidence pages: recall@5, 10 and 20, hit@k and MRR@10, each with a 95% bootstrap interval. The decision metric is **recall@10**; MRR@10 is secondary.
- **Comparisons:** paired permutation tests (10,000 sign flips) against the current baseline, with Holm's adjustment across each family of variants tried, including variants that turned out badly ([ADR-0007](../decisions/0007-evaluation-statistics.md)).
- **One change at a time:** search mode, reranking and neighbouring chunks on `tokens-480`, chunking and late chunking with dense search, then the search modes and the strongest reranker re-checked on the chunking chosen.
- **Machine:** an 8-core laptop CPU. Latency was measured with the machine otherwise idle.

## Results

The floor is the first 20 pages of the right filing: recall@10 0.197, hit@20 0.29.

### Search mode

`tokens-480` chunks, bge-small, oracle document:

| Configuration | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| Dense | **0.485** | **0.608 (0.52 to 0.70)** | **0.713** | **0.740** | 0.307 |
| BM25 | 0.330 | 0.440 (0.35 to 0.54) | 0.545 | 0.570 | 0.208 |
| Hybrid, RRF k = 60 | 0.385 | 0.540 (0.45 to 0.64) | 0.645 | 0.680 | 0.277 |
| Hybrid, RRF weights 2 : 1 | 0.400 | 0.540 (0.45 to 0.64) | 0.668 | 0.710 | **0.309** |

Searching all 84 filings (corpus setting):

| Configuration | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| Dense | **0.170** | **0.345 (0.26 to 0.43)** | **0.500** | **0.540** | 0.115 |
| BM25 | 0.090 | 0.155 (0.09 to 0.23) | 0.210 | 0.230 | 0.081 |
| Hybrid, RRF k = 60 | 0.125 | 0.210 (0.14 to 0.29) | 0.350 | 0.380 | **0.118** |

Recall@10 by question type (oracle document):

| Question type | Questions | Dense | BM25 | Hybrid |
|---|---|---|---|---|
| Domain-relevant | 34 | 0.392 | 0.191 | 0.235 |
| Metrics-generated | 33 | 0.742 | 0.379 | 0.636 |
| Novel-generated | 33 | 0.697 | 0.758 | 0.758 |

### Reranking

Dense search's top candidates reordered by a cross-encoder, `tokens-480`, oracle document:

| Reranker (candidates) | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| None (dense) | **0.485** | **0.608 (0.52 to 0.70)** | 0.713 | 0.740 | **0.307** |
| ms-marco-MiniLM-L-6-v2 (30) | 0.390 | 0.510 (0.41 to 0.60) | 0.678 | 0.700 | 0.264 |
| jina-reranker-v1-turbo-en (30) | 0.380 | 0.580 (0.48 to 0.67) | **0.728** | **0.750** | 0.304 |
| bge-reranker-base (20) | 0.435 | 0.605 (0.52 to 0.70) | 0.703 | 0.740 | 0.284 |

### Neighbouring chunks

Each of the top 5 dense hits followed by the chunk before and after it: recall@10 0.575 (0.48 to 0.67) against 0.608, MRR 0.284 against 0.307.

### Chunking

Dense search with bge-small, oracle document, counted over the 58 dev filings:

| Strategy | Chunks | Median tokens | Cross a page | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|---|---|---|
| `tokens-480` | 15,422 | 462 | 51% | 0.485 | 0.608 (0.52 to 0.70) | 0.713 | 0.740 | 0.307 |
| **`page`** | 16,584 | 450 | 0% | 0.530 | 0.630 (0.54 to 0.72) | 0.760 | 0.770 | 0.423 |
| `tokens-256` | 27,910 | 243 | 29% | 0.490 | 0.640 (0.55 to 0.73) | 0.748 | 0.770 | 0.377 |
| `semantic` | 17,743 | 375 | 25% | 0.485 | 0.610 (0.52 to 0.70) | 0.715 | 0.730 | 0.364 |

MRR@10 by question type:

| Question type | `tokens-480` | `page` | `tokens-256` | `semantic` |
|---|---|---|---|---|
| Domain-relevant | 0.158 | 0.229 | 0.214 | 0.303 |
| Metrics-generated | 0.423 | 0.604 | 0.428 | 0.521 |
| Novel-generated | 0.345 | 0.440 | 0.494 | 0.270 |

Page chunks gain most on metrics questions, whose evidence is usually one financial statement: a page chunk holds the whole statement with its title, and its page is the evidence page by construction. A 480-token chunk that spans pages 59 and 60 lists its most-covered page first, which is not always the one with the answer.

### Late chunking

jina-embeddings-v2-small-en on the same `tokens-480` chunks, oracle document:

| Embedding | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| bge-small, chunk by chunk (reference) | 0.485 | 0.608 (0.52 to 0.70) | 0.713 | 0.740 | 0.307 |
| jina-v2-small, chunk by chunk | 0.475 | 0.593 (0.50 to 0.69) | 0.767 | 0.790 | 0.337 |
| jina-v2-small, late-chunked | 0.453 | 0.613 (0.52 to 0.70) | 0.770 | 0.790 | 0.328 |

Late chunking raised recall@10 on the generic domain questions, where context should matter most (0.304 to 0.377), and lowered it slightly on metrics questions (0.742 to 0.727); overall the difference is within noise.

### Re-checked on page chunks

The search modes and the strongest reranker again, on the chunking chosen:

| Configuration | recall@5 | recall@10 (95% interval) | recall@20 | hit@20 | MRR@10 |
|---|---|---|---|---|---|
| Dense, own filing | **0.530** | **0.630 (0.54 to 0.72)** | **0.760** | **0.770** | **0.423** |
| BM25, own filing | 0.305 | 0.430 (0.34 to 0.53) | 0.565 | 0.600 | 0.243 |
| Hybrid, own filing | 0.465 | 0.585 (0.49 to 0.68) | 0.680 | 0.710 | 0.334 |
| Dense + bge-reranker-base (20), own filing | 0.470 | 0.615 (0.52 to 0.70) | 0.760 | 0.770 | 0.335 |
| Dense, all 84 filings | **0.305** | **0.415 (0.33 to 0.51)** | **0.495** | **0.520** | **0.230** |
| BM25, all 84 filings | 0.125 | 0.185 (0.12 to 0.26) | 0.245 | 0.250 | 0.100 |
| Hybrid, all 84 filings | 0.215 | 0.315 (0.23 to 0.41) | 0.440 | 0.470 | 0.150 |

### Latency

Per question, from the client: query embedding, search and any reranking. Differences of about 10 ms are within the run-to-run variation.

| Configuration | p50 ms | p95 ms |
|---|---|---|
| BM25, `tokens-480`, own filing | 17 | 31 |
| Dense, `tokens-480`, own filing | 56 | 83 |
| Dense, `page`, own filing | 49 | 81 |
| Hybrid, `tokens-480`, own filing | 53 | 83 |
| Dense, `page`, all 84 filings | 41 | 52 |
| Hybrid, `page`, all 84 filings | 57 | 79 |
| Dense + neighbouring chunks | 78 | 115 |
| Dense, jina-v2-small (late-chunked index), own filing | 28 | 44 |
| Dense + MiniLM-L6 over 30 | 2,576 | 3,258 |
| Dense + jina-turbo over 30 | 3,392 | 4,728 |
| Dense + bge-reranker-base over 20 | 8,675 | 9,050 |

## Comparison

Paired against the configuration each family changes, Holm-adjusted within each family.

**Search mode, `tokens-480`, oracle document** (recall@10, 3 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-oracle` | 0.608 | 0.440 | -0.168 (-0.263 to -0.075) | 0.0007 | 0.0021 | worse |
| `tokens-480_bge-small-hybrid-oracle` | 0.608 | 0.540 | -0.068 (-0.145 to +0.008) | 0.1021 | 0.1820 | no significant difference |
| `tokens-480_bge-small-hybrid-w2-1-oracle` | 0.608 | 0.540 | -0.068 (-0.142 to +0.005) | 0.0910 | 0.1820 | no significant difference |

**Search mode, `tokens-480`, corpus** (recall@10, 2 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-corpus` | 0.345 | 0.155 | -0.190 (-0.280 to -0.095) | 0.0003 | 0.0006 | worse |
| `tokens-480_bge-small-hybrid-corpus` | 0.345 | 0.210 | -0.135 (-0.225 to -0.045) | 0.0071 | 0.0071 | worse |

**Reranking, `tokens-480`, oracle document** (recall@10, 3 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-rerank-minilm-l6-oracle` | 0.608 | 0.510 | -0.098 (-0.185 to -0.013) | 0.0326 | 0.0978 | no significant difference |
| `tokens-480_bge-small-dense-rerank-jina-turbo-oracle` | 0.608 | 0.580 | -0.028 (-0.113 to +0.057) | 0.5664 | 1.0000 | no significant difference |
| `tokens-480_bge-small-dense-rerank-bge-base-oracle` | 0.608 | 0.605 | -0.003 (-0.072 to +0.060) | 1.0000 | 1.0000 | no significant difference |

**Neighbouring chunks, oracle document** (recall@10, 1 comparison):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-nb1-oracle` | 0.608 | 0.575 | -0.033 (-0.092 to +0.023) | 0.3128 | 0.3128 | no significant difference |

**Chunking, dense search, oracle document** (3 comparisons), recall@10 and then MRR@10:

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-oracle` | 0.608 | 0.630 | +0.022 (-0.043 to +0.088) | 0.5573 | 1.0000 | no significant difference |
| `tokens-256_bge-small-dense-oracle` | 0.608 | 0.640 | +0.032 (-0.040 to +0.105) | 0.4225 | 1.0000 | no significant difference |
| `semantic_bge-small-dense-oracle` | 0.608 | 0.610 | +0.002 (-0.063 to +0.070) | 1.0000 | 1.0000 | no significant difference |

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-oracle` | 0.307 | 0.423 | +0.115 (+0.048 to +0.184) | 0.0010 | 0.0030 | better |
| `tokens-256_bge-small-dense-oracle` | 0.307 | 0.377 | +0.070 (+0.011 to +0.128) | 0.0184 | 0.0368 | better |
| `semantic_bge-small-dense-oracle` | 0.307 | 0.364 | +0.057 (-0.008 to +0.122) | 0.0952 | 0.0952 | no significant difference |

**Chunking, dense search, corpus** (1 comparison), recall@10 and then MRR@10:

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-corpus` | 0.345 | 0.415 | +0.070 (-0.010 to +0.155) | 0.1100 | 0.1100 | no significant difference |

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-corpus` | 0.115 | 0.230 | +0.115 (+0.065 to +0.170) | 0.0001 | 0.0001 | better |

**Late chunking, jina-v2-small** (1 comparison), recall@10 and then MRR@10:

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-late-dense-oracle` | 0.593 | 0.613 | +0.020 (-0.050 to +0.090) | 0.6796 | 0.6796 | no significant difference |

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-late-dense-oracle` | 0.337 | 0.328 | -0.009 (-0.068 to +0.048) | 0.7537 | 0.7537 | no significant difference |

**Embedding model, `tokens-480`** (recall@10, 1 comparison):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-dense-oracle` | 0.608 | 0.593 | -0.015 (-0.095 to +0.060) | 0.8057 | 0.8057 | no significant difference |

**Page chunks: search mode and reranking, oracle document** (3 comparisons), recall@10 and then MRR@10:

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-oracle` | 0.630 | 0.430 | -0.200 (-0.300 to -0.105) | 0.0002 | 0.0006 | worse |
| `page_bge-small-hybrid-oracle` | 0.630 | 0.585 | -0.045 (-0.115 to +0.020) | 0.2494 | 0.4988 | no significant difference |
| `page_bge-small-dense-rerank-bge-base-oracle` | 0.630 | 0.615 | -0.015 (-0.080 to +0.050) | 0.7670 | 0.7670 | no significant difference |

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-oracle` | 0.423 | 0.243 | -0.180 (-0.267 to -0.094) | 0.0002 | 0.0006 | worse |
| `page_bge-small-hybrid-oracle` | 0.423 | 0.334 | -0.089 (-0.156 to -0.026) | 0.0092 | 0.0184 | worse |
| `page_bge-small-dense-rerank-bge-base-oracle` | 0.423 | 0.335 | -0.088 (-0.154 to -0.022) | 0.0100 | 0.0184 | worse |

**Page chunks: search mode, corpus** (recall@10, 2 comparisons):

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-corpus` | 0.415 | 0.185 | -0.230 (-0.335 to -0.125) | 0.0002 | 0.0004 | worse |
| `page_bge-small-hybrid-corpus` | 0.415 | 0.315 | -0.100 (-0.180 to -0.020) | 0.0206 | 0.0206 | worse |

## Decision

The doc agent starts from **dense search with bge-small over page chunks**, without BM25 fusion, a reranker or late chunking ([ADR-0011](../decisions/0011-retrieval-baseline.md)).

- On the decision metric, recall@10, no variant beat `tokens-480` significantly. With that tied, the secondary metric decided: page chunks rank the first evidence page significantly higher within the filing (MRR@10 0.423 against 0.307) and across all filings (0.230 against 0.115), are never worse on any metric, and make every citation an exact page.
- On page chunks, hybrid search and bge-reranker-base lower MRR@10 significantly, and BM25 is worse on every metric, so neither fusion nor reranking joins the baseline.
- Neighbouring chunks stay in the design for building the answer's context in Phase 3, where answer quality, not page recall, measures them.

## Why nothing beat dense search

Apart from chunking, every challenger lost or tied, and the breakdown by question type points at the questions more than at the methods:

- **FinanceBench's templates.** Two thirds of the dev questions are generated from templates that add instructions to the actual question: "Give a response to the question by relying on the details shown in the cash flow statement", "Round your answer to two decimal places", "If operating margin is not a useful metric for a company like this, then state that and explain why". To BM25 those words are as important as "capital expenditure", and they match pages all over every filing. On the human-written *novel* questions, which carry no template, BM25 beats dense search (0.758 against 0.697 on `tokens-480`, 0.803 against 0.758 on page chunks).
- **Rerankers read the same noise, and less of the chunk.** MS MARCO cross-encoders were trained on short web queries and paragraph-length passages. MiniLM reads at most 512 tokens of question plus chunk, so a 480-token chunk loses its end; jina-turbo reads everything and loses less (0.580 against 0.510). bge-reranker-base, more than ten times MiniLM's size, ties dense search on `tokens-480` (0.605) because its gains and losses cancel: better on the human-written questions (0.773 against 0.697), worse on the templated domain questions (0.294 against 0.392). It also costs about 9 seconds a question on a laptop CPU.
- **The hard questions need reasoning about where to look.** With page chunks, 23 questions still have no evidence page in the top 20, most of them domain-relevant, such as "Does 3M have a reasonably healthy liquidity profile based on its quick ratio?". The evidence is a balance sheet, and nothing in the question's words says so.
- **Finding the filing is a problem of its own.** Searching all 84 filings instead of the right one drops page chunks' hit@20 from 0.77 to 0.52.

These point to Phase 3's query understanding (company, period and form as filters) and query rewriting (turning a templated question into what to look for), after which hybrid search and reranking deserve another look.

## Logs

Every run is in `eval/results/retrieval/<run>/dev/` (`summary.md` for reading, `items.jsonl` with each question's retrieved pages), and the comparison tables in `eval/results/retrieval/_comparisons/`. Reproduce a run with `uv run poe run-retrieval` and the options in its `summary.json`; dense, BM25 and hybrid runs repeat exactly.
