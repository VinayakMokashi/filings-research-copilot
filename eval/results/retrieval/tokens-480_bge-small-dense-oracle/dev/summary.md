# retrieval: tokens-480_bge-small-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 14:42 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.485 | 0.390 to 0.580 |
| recall@10 | 0.608 | 0.515 to 0.697 |
| recall@20 | 0.713 | 0.625 to 0.795 |
| hit@5 | 0.520 | 0.420 to 0.620 |
| hit@10 | 0.650 | 0.560 to 0.740 |
| hit@20 | 0.740 | 0.650 to 0.820 |
| mrr@10 | 0.307 | 0.242 to 0.379 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.250 (0.12 to 0.40) | 0.392 (0.25 to 0.54) | 0.466 (0.30 to 0.63) | 0.294 (0.15 to 0.44) | 0.471 (0.29 to 0.65) | 0.500 (0.32 to 0.68) | 0.158 (0.08 to 0.25) |
| metrics-generated | 33 | 0.667 (0.52 to 0.82) | 0.742 (0.61 to 0.88) | 0.864 (0.76 to 0.95) | 0.727 (0.58 to 0.88) | 0.788 (0.64 to 0.91) | 0.909 (0.79 to 1.00) | 0.423 (0.30 to 0.55) |
| novel-generated | 33 | 0.545 (0.36 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.545 (0.36 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.345 (0.23 to 0.47) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 1,
  "late_chunking": false,
  "latency_ms": {
    "mean": 224.0,
    "p50": 205.6,
    "p95": 421.2
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
