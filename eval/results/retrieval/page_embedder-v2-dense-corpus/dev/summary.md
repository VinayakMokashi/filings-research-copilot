# retrieval: page_embedder-v2-dense-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 21:20 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.235 | 0.160 to 0.320 |
| recall@10 | 0.335 | 0.250 to 0.425 |
| recall@20 | 0.395 | 0.305 to 0.490 |
| hit@5 | 0.260 | 0.180 to 0.350 |
| hit@10 | 0.370 | 0.270 to 0.470 |
| hit@20 | 0.430 | 0.330 to 0.530 |
| mrr@10 | 0.162 | 0.108 to 0.223 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.147 (0.04 to 0.26) | 0.147 (0.04 to 0.26) | 0.250 (0.12 to 0.40) | 0.176 (0.06 to 0.32) | 0.176 (0.06 to 0.32) | 0.265 (0.12 to 0.41) | 0.084 (0.02 to 0.16) |
| metrics-generated | 33 | 0.348 (0.20 to 0.50) | 0.530 (0.38 to 0.70) | 0.530 (0.38 to 0.70) | 0.394 (0.24 to 0.55) | 0.606 (0.42 to 0.76) | 0.606 (0.42 to 0.76) | 0.249 (0.15 to 0.36) |
| novel-generated | 33 | 0.212 (0.09 to 0.36) | 0.333 (0.18 to 0.48) | 0.409 (0.24 to 0.58) | 0.212 (0.09 to 0.36) | 0.333 (0.18 to 0.48) | 0.424 (0.24 to 0.58) | 0.156 (0.07 to 0.27) |

## System

```json
{
  "collection": "fb_page_embedder-v2",
  "dense_model": "embedder-v2: bge-small-en-v1.5 fine-tuned on filings, with negatives from other companies",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 34.3,
    "p50": 31.9,
    "p95": 49.7
  },
  "mode": "dense",
  "setting": "corpus",
  "strategy": "page"
}
```
