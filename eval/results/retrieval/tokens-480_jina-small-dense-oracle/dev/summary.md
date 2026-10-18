# retrieval: tokens-480_jina-small-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 20:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.475 | 0.380 to 0.570 |
| recall@10 | 0.593 | 0.500 to 0.688 |
| recall@20 | 0.767 | 0.687 to 0.845 |
| hit@5 | 0.500 | 0.400 to 0.600 |
| hit@10 | 0.620 | 0.530 to 0.710 |
| hit@20 | 0.790 | 0.710 to 0.870 |
| mrr@10 | 0.337 | 0.265 to 0.410 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.206 (0.09 to 0.34) | 0.304 (0.16 to 0.46) | 0.549 (0.39 to 0.71) | 0.235 (0.09 to 0.38) | 0.353 (0.21 to 0.50) | 0.588 (0.41 to 0.74) | 0.144 (0.06 to 0.24) |
| metrics-generated | 33 | 0.621 (0.45 to 0.77) | 0.742 (0.59 to 0.88) | 0.909 (0.82 to 0.98) | 0.667 (0.52 to 0.82) | 0.758 (0.61 to 0.88) | 0.939 (0.85 to 1.00) | 0.523 (0.38 to 0.66) |
| novel-generated | 33 | 0.606 (0.42 to 0.76) | 0.742 (0.59 to 0.88) | 0.848 (0.73 to 0.97) | 0.606 (0.42 to 0.76) | 0.758 (0.61 to 0.91) | 0.848 (0.73 to 0.97) | 0.350 (0.24 to 0.46) |

## System

```json
{
  "collection": "fb_tokens-480_jina-small",
  "dense_model": "jinaai/jina-embeddings-v2-small-en",
  "fetched_chunks": 60,
  "index_documents": 58,
  "late_chunking": false,
  "latency_ms": {
    "mean": 30.0,
    "p50": 28.5,
    "p95": 43.1
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
