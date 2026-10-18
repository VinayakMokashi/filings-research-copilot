# retrieval: page_bge-small-dense-rerank-bge-base-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 20:36 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.470 | 0.375 to 0.565 |
| recall@10 | 0.615 | 0.520 to 0.705 |
| recall@20 | 0.760 | 0.675 to 0.840 |
| hit@5 | 0.500 | 0.400 to 0.600 |
| hit@10 | 0.640 | 0.550 to 0.730 |
| hit@20 | 0.770 | 0.680 to 0.850 |
| mrr@10 | 0.335 | 0.262 to 0.412 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.206 (0.09 to 0.35) | 0.353 (0.21 to 0.51) | 0.574 (0.41 to 0.74) | 0.206 (0.09 to 0.35) | 0.382 (0.24 to 0.56) | 0.588 (0.41 to 0.74) | 0.091 (0.05 to 0.14) |
| metrics-generated | 33 | 0.652 (0.50 to 0.79) | 0.803 (0.67 to 0.92) | 0.894 (0.79 to 0.98) | 0.727 (0.58 to 0.88) | 0.848 (0.73 to 0.97) | 0.909 (0.79 to 1.00) | 0.551 (0.41 to 0.69) |
| novel-generated | 33 | 0.561 (0.39 to 0.73) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.576 (0.39 to 0.73) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.370 (0.24 to 0.50) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 58,
  "late_chunking": false,
  "latency_ms": {
    "mean": 7714.0,
    "p50": 7813.6,
    "p95": 8678.2
  },
  "mode": "dense",
  "rerank_top": 20,
  "reranker": "BAAI/bge-reranker-base",
  "setting": "oracle",
  "strategy": "page"
}
```
