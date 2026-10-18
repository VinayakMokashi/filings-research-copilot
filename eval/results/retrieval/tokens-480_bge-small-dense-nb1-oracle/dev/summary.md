# retrieval: tokens-480_bge-small-dense-nb1-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 19:56 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.440 | 0.350 to 0.530 |
| recall@10 | 0.575 | 0.480 to 0.670 |
| recall@20 | 0.698 | 0.608 to 0.783 |
| hit@5 | 0.470 | 0.370 to 0.570 |
| hit@10 | 0.590 | 0.490 to 0.680 |
| hit@20 | 0.720 | 0.630 to 0.800 |
| mrr@10 | 0.284 | 0.218 to 0.356 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.221 (0.09 to 0.37) | 0.309 (0.16 to 0.47) | 0.436 (0.28 to 0.60) | 0.235 (0.09 to 0.38) | 0.324 (0.18 to 0.47) | 0.471 (0.29 to 0.65) | 0.124 (0.05 to 0.22) |
| metrics-generated | 33 | 0.576 (0.41 to 0.73) | 0.727 (0.58 to 0.86) | 0.848 (0.73 to 0.95) | 0.636 (0.45 to 0.79) | 0.758 (0.61 to 0.91) | 0.879 (0.76 to 0.97) | 0.404 (0.28 to 0.53) |
| novel-generated | 33 | 0.530 (0.36 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.545 (0.36 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.331 (0.21 to 0.46) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 81.3,
    "p50": 78.5,
    "p95": 115.0
  },
  "mode": "dense",
  "neighbours": 1,
  "neighbours_top": 5,
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
