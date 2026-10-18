# retrieval: tokens-256_bge-small-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 20:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.490 | 0.395 to 0.585 |
| recall@10 | 0.640 | 0.550 to 0.730 |
| recall@20 | 0.748 | 0.665 to 0.830 |
| hit@5 | 0.520 | 0.420 to 0.620 |
| hit@10 | 0.670 | 0.580 to 0.760 |
| hit@20 | 0.770 | 0.690 to 0.850 |
| mrr@10 | 0.377 | 0.300 to 0.455 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.279 (0.15 to 0.43) | 0.397 (0.24 to 0.56) | 0.554 (0.39 to 0.72) | 0.294 (0.15 to 0.44) | 0.412 (0.26 to 0.59) | 0.588 (0.41 to 0.76) | 0.214 (0.10 to 0.34) |
| metrics-generated | 33 | 0.561 (0.41 to 0.71) | 0.712 (0.58 to 0.85) | 0.848 (0.73 to 0.95) | 0.636 (0.45 to 0.79) | 0.788 (0.64 to 0.91) | 0.879 (0.76 to 0.97) | 0.428 (0.31 to 0.56) |
| novel-generated | 33 | 0.636 (0.48 to 0.79) | 0.818 (0.67 to 0.94) | 0.848 (0.73 to 0.97) | 0.636 (0.48 to 0.79) | 0.818 (0.67 to 0.94) | 0.848 (0.73 to 0.97) | 0.494 (0.36 to 0.63) |

## System

```json
{
  "collection": "fb_tokens-256_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 58,
  "late_chunking": false,
  "latency_ms": {
    "mean": 36.8,
    "p50": 33.9,
    "p95": 52.2
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "tokens-256"
}
```
