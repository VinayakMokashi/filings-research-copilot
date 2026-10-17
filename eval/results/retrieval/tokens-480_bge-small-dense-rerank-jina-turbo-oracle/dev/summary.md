# retrieval: tokens-480_bge-small-dense-rerank-jina-turbo-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 15:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.380 | 0.290 to 0.475 |
| recall@10 | 0.580 | 0.485 to 0.670 |
| recall@20 | 0.728 | 0.643 to 0.810 |
| hit@5 | 0.420 | 0.320 to 0.520 |
| hit@10 | 0.610 | 0.510 to 0.700 |
| hit@20 | 0.750 | 0.660 to 0.830 |
| mrr@10 | 0.304 | 0.231 to 0.382 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.118 (0.03 to 0.22) | 0.279 (0.15 to 0.43) | 0.436 (0.27 to 0.60) | 0.147 (0.03 to 0.26) | 0.324 (0.18 to 0.50) | 0.471 (0.29 to 0.65) | 0.107 (0.04 to 0.20) |
| metrics-generated | 33 | 0.545 (0.39 to 0.70) | 0.712 (0.56 to 0.85) | 0.879 (0.77 to 0.97) | 0.636 (0.48 to 0.79) | 0.758 (0.61 to 0.88) | 0.909 (0.79 to 1.00) | 0.461 (0.32 to 0.60) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.758 (0.61 to 0.91) | 0.879 (0.76 to 0.97) | 0.485 (0.30 to 0.67) | 0.758 (0.61 to 0.91) | 0.879 (0.76 to 0.97) | 0.349 (0.23 to 0.48) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 1,
  "late_chunking": false,
  "latency_ms": {
    "mean": 13781.9,
    "p50": 13630.8,
    "p95": 20282.3
  },
  "mode": "dense",
  "rerank_top": 30,
  "reranker": "jinaai/jina-reranker-v1-turbo-en",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
