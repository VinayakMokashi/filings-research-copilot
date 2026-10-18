# retrieval: tokens-480_bge-small-bm25-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.330 | 0.240 to 0.420 |
| recall@10 | 0.440 | 0.350 to 0.535 |
| recall@20 | 0.545 | 0.450 to 0.640 |
| hit@5 | 0.350 | 0.260 to 0.440 |
| hit@10 | 0.480 | 0.380 to 0.580 |
| hit@20 | 0.570 | 0.470 to 0.660 |
| mrr@10 | 0.208 | 0.147 to 0.273 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.32) | 0.191 (0.07 to 0.32) | 0.324 (0.18 to 0.49) | 0.176 (0.06 to 0.32) | 0.206 (0.09 to 0.35) | 0.353 (0.21 to 0.53) | 0.117 (0.03 to 0.22) |
| metrics-generated | 33 | 0.242 (0.12 to 0.39) | 0.379 (0.24 to 0.53) | 0.515 (0.35 to 0.68) | 0.303 (0.15 to 0.45) | 0.485 (0.30 to 0.67) | 0.545 (0.36 to 0.73) | 0.178 (0.09 to 0.28) |
| novel-generated | 33 | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.803 (0.67 to 0.92) | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.331 (0.22 to 0.45) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 18.5,
    "p50": 17.2,
    "p95": 30.8
  },
  "mode": "bm25",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
