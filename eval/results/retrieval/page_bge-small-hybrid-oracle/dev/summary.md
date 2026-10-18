# retrieval: page_bge-small-hybrid-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:27 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.465 | 0.370 to 0.560 |
| recall@10 | 0.585 | 0.490 to 0.675 |
| recall@20 | 0.680 | 0.590 to 0.765 |
| hit@5 | 0.510 | 0.410 to 0.610 |
| hit@10 | 0.620 | 0.520 to 0.710 |
| hit@20 | 0.710 | 0.620 to 0.800 |
| mrr@10 | 0.334 | 0.260 to 0.410 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.235 (0.10 to 0.38) | 0.309 (0.16 to 0.47) | 0.471 (0.31 to 0.63) | 0.265 (0.12 to 0.41) | 0.353 (0.21 to 0.53) | 0.500 (0.32 to 0.68) | 0.167 (0.07 to 0.28) |
| metrics-generated | 33 | 0.576 (0.42 to 0.73) | 0.697 (0.56 to 0.83) | 0.758 (0.62 to 0.88) | 0.667 (0.52 to 0.82) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.379 (0.26 to 0.50) |
| novel-generated | 33 | 0.591 (0.42 to 0.76) | 0.758 (0.61 to 0.88) | 0.818 (0.67 to 0.94) | 0.606 (0.42 to 0.76) | 0.758 (0.61 to 0.88) | 0.818 (0.67 to 0.94) | 0.461 (0.32 to 0.61) |

## System

```json
{
  "candidates_per_ranking": 50,
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 55.2,
    "p50": 55.0,
    "p95": 70.7
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "setting": "oracle",
  "strategy": "page"
}
```
