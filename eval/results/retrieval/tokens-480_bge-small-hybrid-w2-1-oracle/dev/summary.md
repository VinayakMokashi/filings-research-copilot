# retrieval: tokens-480_bge-small-hybrid-w2-1-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 15:02 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.405 | 0.315 to 0.495 |
| recall@10 | 0.470 | 0.375 to 0.565 |
| recall@20 | 0.643 | 0.553 to 0.730 |
| hit@5 | 0.440 | 0.340 to 0.540 |
| hit@10 | 0.490 | 0.390 to 0.590 |
| hit@20 | 0.680 | 0.590 to 0.770 |
| mrr@10 | 0.252 | 0.186 to 0.323 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.31) | 0.206 (0.09 to 0.34) | 0.348 (0.21 to 0.50) | 0.206 (0.09 to 0.35) | 0.235 (0.09 to 0.38) | 0.412 (0.24 to 0.59) | 0.122 (0.04 to 0.23) |
| metrics-generated | 33 | 0.439 (0.29 to 0.59) | 0.485 (0.32 to 0.65) | 0.742 (0.61 to 0.88) | 0.515 (0.33 to 0.70) | 0.515 (0.33 to 0.70) | 0.788 (0.64 to 0.91) | 0.316 (0.19 to 0.45) |
| novel-generated | 33 | 0.606 (0.42 to 0.76) | 0.727 (0.58 to 0.88) | 0.848 (0.73 to 0.97) | 0.606 (0.42 to 0.76) | 0.727 (0.58 to 0.88) | 0.848 (0.73 to 0.97) | 0.322 (0.21 to 0.45) |

## System

```json
{
  "candidates_per_ranking": 50,
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 1,
  "late_chunking": false,
  "latency_ms": {
    "mean": 274.6,
    "p50": 257.2,
    "p95": 438.6
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
