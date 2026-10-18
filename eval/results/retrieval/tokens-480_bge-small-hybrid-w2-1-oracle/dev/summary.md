# retrieval: tokens-480_bge-small-hybrid-w2-1-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:28 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.400 | 0.310 to 0.495 |
| recall@10 | 0.540 | 0.445 to 0.635 |
| recall@20 | 0.668 | 0.580 to 0.755 |
| hit@5 | 0.430 | 0.340 to 0.530 |
| hit@10 | 0.580 | 0.480 to 0.680 |
| hit@20 | 0.710 | 0.620 to 0.800 |
| mrr@10 | 0.309 | 0.234 to 0.388 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.31) | 0.250 (0.12 to 0.40) | 0.392 (0.25 to 0.54) | 0.206 (0.09 to 0.35) | 0.294 (0.15 to 0.44) | 0.471 (0.29 to 0.65) | 0.135 (0.05 to 0.24) |
| metrics-generated | 33 | 0.455 (0.29 to 0.62) | 0.636 (0.48 to 0.79) | 0.773 (0.64 to 0.89) | 0.515 (0.33 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.391 (0.26 to 0.53) |
| novel-generated | 33 | 0.576 (0.39 to 0.73) | 0.742 (0.59 to 0.88) | 0.848 (0.73 to 0.97) | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.848 (0.73 to 0.97) | 0.405 (0.28 to 0.54) |

## System

```json
{
  "candidates_per_ranking": 50,
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 54.4,
    "p50": 54.0,
    "p95": 71.1
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "rrf_weights": {
    "bm25": 1.0,
    "dense": 2.0
  },
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
