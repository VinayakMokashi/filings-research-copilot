# retrieval: semantic_bge-small-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 20:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.485 | 0.390 to 0.580 |
| recall@10 | 0.610 | 0.520 to 0.700 |
| recall@20 | 0.715 | 0.630 to 0.800 |
| hit@5 | 0.530 | 0.430 to 0.630 |
| hit@10 | 0.650 | 0.550 to 0.740 |
| hit@20 | 0.730 | 0.640 to 0.810 |
| mrr@10 | 0.364 | 0.289 to 0.440 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.338 (0.19 to 0.50) | 0.397 (0.25 to 0.56) | 0.485 (0.32 to 0.65) | 0.382 (0.24 to 0.56) | 0.441 (0.29 to 0.62) | 0.500 (0.32 to 0.68) | 0.303 (0.17 to 0.45) |
| metrics-generated | 33 | 0.697 (0.56 to 0.83) | 0.758 (0.62 to 0.88) | 0.818 (0.68 to 0.94) | 0.788 (0.64 to 0.91) | 0.818 (0.67 to 0.94) | 0.848 (0.73 to 0.97) | 0.521 (0.39 to 0.65) |
| novel-generated | 33 | 0.424 (0.27 to 0.61) | 0.682 (0.52 to 0.83) | 0.848 (0.73 to 0.97) | 0.424 (0.27 to 0.61) | 0.697 (0.55 to 0.85) | 0.848 (0.73 to 0.97) | 0.270 (0.17 to 0.39) |

## System

```json
{
  "collection": "fb_semantic_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 58,
  "late_chunking": false,
  "latency_ms": {
    "mean": 37.7,
    "p50": 35.1,
    "p95": 54.7
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "semantic"
}
```
