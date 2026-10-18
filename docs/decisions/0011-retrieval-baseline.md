# ADR-0011: Start the doc agent from dense search over page chunks

- **Status:** Accepted
- **Date:** 2026-10-18
- **Phase:** 2

## Context

Phase 3's doc agent needs a retrieval setup to start from: how filings are chunked, how chunks are searched, and whether a reranker reorders them. Phase 2 built the pieces (ADR-0009 parsing, ADR-0010 the index) and measured them on the 100 FinanceBench dev questions, scoring the evidence pages each configuration finds within the question's own filing. The decision metric was declared up front as recall@10, compared with paired permutation tests and Holm's adjustment across each family of variants tried ([ADR-0007](0007-evaluation-statistics.md)). MRR@10, how high the first evidence page ranks, was the secondary metric.

## Options considered

| Question | Options measured |
|---|---|
| Chunking (dense search) | `tokens-480` (480-token windows, 64 overlap), `page` (one chunk per page, long pages split within the page), `tokens-256` (256-token windows, 32 overlap), `semantic` (breaks where neighbouring sentences' embeddings drift apart) |
| Context in the vectors | jina-embeddings-v2-small-en, chunk by chunk or late-chunked (2,048-token windows) |
| Search mode | dense (bge-small), BM25, hybrid with RRF (k = 60), hybrid with weights |
| Reranking | none, ms-marco-MiniLM-L-6-v2, jina-reranker-v1-turbo-en, bge-reranker-base |
| Context expansion | the chunks before and after each top hit |

## Decision

The doc agent starts from **dense bge-small search over page chunks**, with no BM25 fusion, no reranker and no late chunking. Neighbouring chunks are kept for building the answer's context in Phase 3, not for ranking.

## Evidence

All on FinanceBench dev, oracle-document setting; full tables in the [retrieval report](../eval/retrieval-baseline.md).

- **Chunking.** No strategy beat `tokens-480` significantly on recall@10 (page 0.630, `tokens-256` 0.640, semantic 0.610, against 0.608). On MRR@10, page chunks were significantly better (0.423 against 0.307, +0.115, Holm-adjusted p = 0.003), as were `tokens-256` (0.377, p = 0.037); semantic chunks were not (0.364). Across all 84 filings, page chunks doubled MRR@10 (0.230 against 0.115, p = 0.0001). With the decision metric tied, the secondary metric decides, and page chunks win it by the widest margin: the answer model reads the top few chunks, so ranking the evidence first matters. Page chunks also make every citation an exact page, because a chunk never spans two.
- **Late chunking.** Against the same model chunk by chunk, late chunking changed recall@10 by +0.020 and MRR@10 by −0.009, neither significant. It helped the generic domain questions (recall@10 0.304 to 0.377) and slightly hurt the metrics questions. jina-v2-small itself was no better than bge-small (0.593 against 0.608).
- **Search mode and reranking.** On `tokens-480`, BM25 was significantly worse than dense search (recall@10 0.440 against 0.608), and equal-weight hybrid search (0.540) and the three rerankers (MiniLM-L6 0.510, jina-turbo 0.580, bge-reranker-base 0.605) were not significantly different. Re-checked on page chunks, hybrid search and bge-reranker-base both lowered MRR@10 significantly (0.334 and 0.335 against 0.423, Holm-adjusted p = 0.018), and across all 84 filings hybrid search was significantly worse on recall@10 (0.315 against 0.415).
- **Context expansion.** Adding neighbouring chunks after the top 5 hits changed recall@10 by −0.033 (not significant): extra pages take ranking slots.
- **Cost.** Dense search over page chunks answers in about 50 ms a question on a laptop CPU, embedding included. A cross-encoder adds 2.6 seconds (MiniLM over 30 candidates) to 8.7 seconds (bge-reranker-base over 20).

## Consequences

- The main collection for Phase 3 is `fb_page_bge-small`, indexed for all 84 question filings.
- Dense search alone leaves 23 of 100 dev questions with no evidence page in the top 20 even within the right filing, and searching all 84 filings drops hit@20 from 0.77 to 0.52. Phase 3 starts there: query understanding (company, period and form as filters) and query rewriting.
- Hybrid search and reranking stay in the code and get re-measured after query rewriting, because their weakness here traces to FinanceBench's templated questions.
- Phase 7 fine-tunes bge-small on the synthetic pairs and compares it with this baseline.
- If page chunks prove too coarse for answer generation (a 700-token page split in two still carries a lot of text), `tokens-256` is the runner-up on both metrics.

## References

- [Retrieval baseline report](../eval/retrieval-baseline.md) and the comparison tables in `eval/results/retrieval/_comparisons/`.
- Günther et al., [Late Chunking](https://arxiv.org/abs/2409.04701), 2024.
- Cormack, Clarke and Büttcher, Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods, SIGIR 2009.
