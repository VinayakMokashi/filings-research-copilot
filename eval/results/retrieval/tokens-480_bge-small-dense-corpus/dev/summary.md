# retrieval: tokens-480_bge-small-dense-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 15:34 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.170 | 0.100 to 0.245 |
| recall@10 | 0.345 | 0.255 to 0.435 |
| recall@20 | 0.500 | 0.410 to 0.590 |
| hit@5 | 0.190 | 0.110 to 0.270 |
| hit@10 | 0.380 | 0.290 to 0.480 |
| hit@20 | 0.540 | 0.440 to 0.640 |
| mrr@10 | 0.115 | 0.073 to 0.163 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.088 (0.01 to 0.19) | 0.221 (0.10 to 0.35) | 0.338 (0.21 to 0.49) | 0.118 (0.03 to 0.24) | 0.265 (0.12 to 0.41) | 0.412 (0.26 to 0.59) | 0.078 (0.03 to 0.15) |
| metrics-generated | 33 | 0.182 (0.06 to 0.32) | 0.424 (0.27 to 0.58) | 0.652 (0.48 to 0.80) | 0.212 (0.09 to 0.36) | 0.485 (0.30 to 0.67) | 0.697 (0.55 to 0.85) | 0.111 (0.06 to 0.18) |
| novel-generated | 33 | 0.242 (0.09 to 0.39) | 0.394 (0.24 to 0.58) | 0.515 (0.33 to 0.70) | 0.242 (0.09 to 0.39) | 0.394 (0.24 to 0.58) | 0.515 (0.33 to 0.70) | 0.157 (0.07 to 0.26) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 374.9,
    "p50": 338.8,
    "p95": 585.7
  },
  "mode": "dense",
  "setting": "corpus",
  "strategy": "tokens-480"
}
```
