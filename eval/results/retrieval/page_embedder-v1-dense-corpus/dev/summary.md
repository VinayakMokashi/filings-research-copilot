# retrieval: page_embedder-v1-dense-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 20:34 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.215 | 0.140 to 0.295 |
| recall@10 | 0.280 | 0.200 to 0.365 |
| recall@20 | 0.395 | 0.305 to 0.490 |
| hit@5 | 0.240 | 0.160 to 0.330 |
| hit@10 | 0.310 | 0.220 to 0.400 |
| hit@20 | 0.420 | 0.320 to 0.520 |
| mrr@10 | 0.134 | 0.086 to 0.186 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.31) | 0.176 (0.06 to 0.31) | 0.279 (0.13 to 0.43) | 0.206 (0.09 to 0.35) | 0.206 (0.09 to 0.35) | 0.294 (0.15 to 0.44) | 0.099 (0.03 to 0.18) |
| metrics-generated | 33 | 0.197 (0.08 to 0.33) | 0.333 (0.18 to 0.48) | 0.515 (0.36 to 0.68) | 0.242 (0.09 to 0.39) | 0.394 (0.24 to 0.58) | 0.576 (0.39 to 0.76) | 0.145 (0.07 to 0.23) |
| novel-generated | 33 | 0.273 (0.12 to 0.42) | 0.333 (0.18 to 0.48) | 0.394 (0.24 to 0.55) | 0.273 (0.12 to 0.42) | 0.333 (0.18 to 0.48) | 0.394 (0.24 to 0.55) | 0.159 (0.07 to 0.27) |

## System

```json
{
  "collection": "fb_page_embedder-v1",
  "dense_model": "embedder-v1: bge-small-en-v1.5 fine-tuned on filings",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 34.5,
    "p50": 32.1,
    "p95": 50.0
  },
  "mode": "dense",
  "setting": "corpus",
  "strategy": "page"
}
```
