# retrieval: page_bge-small-dense-rerank-bge-base-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:05 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.470 | 0.375 to 0.565 |
| recall@10 | 0.650 | 0.560 to 0.740 |
| recall@20 | 0.787 | 0.707 to 0.862 |
| hit@5 | 0.500 | 0.400 to 0.600 |
| hit@10 | 0.670 | 0.580 to 0.760 |
| hit@20 | 0.800 | 0.720 to 0.880 |
| mrr@10 | 0.335 | 0.263 to 0.411 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.221 (0.09 to 0.37) | 0.441 (0.28 to 0.60) | 0.740 (0.59 to 0.87) | 0.235 (0.09 to 0.38) | 0.471 (0.29 to 0.65) | 0.765 (0.62 to 0.88) | 0.113 (0.06 to 0.17) |
| metrics-generated | 33 | 0.652 (0.50 to 0.80) | 0.909 (0.80 to 0.98) | 0.924 (0.83 to 1.00) | 0.727 (0.58 to 0.88) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.583 (0.45 to 0.72) |
| novel-generated | 33 | 0.545 (0.36 to 0.73) | 0.606 (0.42 to 0.76) | 0.697 (0.55 to 0.85) | 0.545 (0.36 to 0.73) | 0.606 (0.42 to 0.76) | 0.697 (0.55 to 0.85) | 0.314 (0.20 to 0.44) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 12036.2,
    "p50": 12168.4,
    "p95": 16062.9
  },
  "mode": "dense",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "rerank_query": "question",
  "rerank_top": 20,
  "reranker": "BAAI/bge-reranker-base",
  "rewrite": {
    "cache": {
      "hits": 300,
      "misses": 0
    },
    "fusion": "RRF, k = 60, over the question and every rewrite",
    "kinds": [
      "multi",
      "hyde",
      "decompose"
    ],
    "latency_ms_p50": 4239.1,
    "model": "groq/qwen/qwen3.8-27b",
    "prompt_version": "1",
    "tokens": 62688
  },
  "setting": "understood",
  "strategy": "page"
}
```
