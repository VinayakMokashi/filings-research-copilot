# retrieval: page_bge-small-dense-rerank-bge-base-rq-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:18 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.522 | 0.427 to 0.615 |
| recall@10 | 0.692 | 0.603 to 0.777 |
| recall@20 | 0.787 | 0.707 to 0.862 |
| hit@5 | 0.580 | 0.480 to 0.680 |
| hit@10 | 0.720 | 0.630 to 0.810 |
| hit@20 | 0.800 | 0.720 to 0.880 |
| mrr@10 | 0.436 | 0.356 to 0.517 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.387 (0.24 to 0.54) | 0.593 (0.43 to 0.75) | 0.740 (0.59 to 0.87) | 0.441 (0.26 to 0.62) | 0.647 (0.47 to 0.79) | 0.765 (0.62 to 0.88) | 0.324 (0.20 to 0.46) |
| metrics-generated | 33 | 0.788 (0.67 to 0.89) | 0.909 (0.82 to 0.98) | 0.924 (0.83 to 1.00) | 0.909 (0.79 to 1.00) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.694 (0.58 to 0.81) |
| novel-generated | 33 | 0.394 (0.24 to 0.55) | 0.576 (0.39 to 0.73) | 0.697 (0.55 to 0.85) | 0.394 (0.24 to 0.55) | 0.576 (0.39 to 0.73) | 0.697 (0.55 to 0.85) | 0.294 (0.18 to 0.42) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 11859.7,
    "p50": 12067.2,
    "p95": 15679.8
  },
  "mode": "dense",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "rerank_query": "rewrite",
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
