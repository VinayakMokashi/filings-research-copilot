# retrieval: tokens-480_bge-small-dense-rerank-bge-base-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 16:11 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.435 | 0.345 to 0.525 |
| recall@10 | 0.605 | 0.515 to 0.700 |
| recall@20 | 0.703 | 0.617 to 0.785 |
| hit@5 | 0.490 | 0.390 to 0.590 |
| hit@10 | 0.640 | 0.550 to 0.730 |
| hit@20 | 0.740 | 0.650 to 0.820 |
| mrr@10 | 0.284 | 0.219 to 0.353 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.162 (0.06 to 0.28) | 0.294 (0.15 to 0.44) | 0.451 (0.29 to 0.61) | 0.206 (0.09 to 0.35) | 0.324 (0.18 to 0.50) | 0.500 (0.32 to 0.68) | 0.115 (0.05 to 0.19) |
| metrics-generated | 33 | 0.515 (0.36 to 0.67) | 0.758 (0.62 to 0.88) | 0.848 (0.73 to 0.94) | 0.636 (0.45 to 0.79) | 0.818 (0.67 to 0.94) | 0.909 (0.79 to 1.00) | 0.358 (0.25 to 0.47) |
| novel-generated | 33 | 0.636 (0.48 to 0.79) | 0.773 (0.62 to 0.91) | 0.818 (0.67 to 0.94) | 0.636 (0.48 to 0.79) | 0.788 (0.64 to 0.91) | 0.818 (0.67 to 0.94) | 0.384 (0.26 to 0.51) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 25428.2,
    "p50": 25582.0,
    "p95": 30511.9
  },
  "mode": "dense",
  "rerank_top": 20,
  "reranker": "BAAI/bge-reranker-base",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
