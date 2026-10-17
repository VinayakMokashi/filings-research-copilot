# retrieval: tokens-480_bge-small-bm25-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 14:43 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.325 | 0.235 to 0.415 |
| recall@10 | 0.425 | 0.335 to 0.520 |
| recall@20 | 0.540 | 0.445 to 0.635 |
| hit@5 | 0.340 | 0.250 to 0.430 |
| hit@10 | 0.460 | 0.360 to 0.560 |
| hit@20 | 0.570 | 0.470 to 0.670 |
| mrr@10 | 0.205 | 0.144 to 0.271 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.32) | 0.191 (0.07 to 0.32) | 0.324 (0.18 to 0.49) | 0.176 (0.06 to 0.32) | 0.206 (0.09 to 0.35) | 0.353 (0.21 to 0.53) | 0.117 (0.03 to 0.22) |
| metrics-generated | 33 | 0.227 (0.11 to 0.38) | 0.333 (0.20 to 0.48) | 0.470 (0.30 to 0.64) | 0.273 (0.12 to 0.42) | 0.424 (0.27 to 0.61) | 0.515 (0.33 to 0.70) | 0.170 (0.08 to 0.28) |
| novel-generated | 33 | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.833 (0.70 to 0.94) | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.848 (0.73 to 0.97) | 0.331 (0.22 to 0.45) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 1,
  "late_chunking": false,
  "latency_ms": {
    "mean": 47.1,
    "p50": 45.3,
    "p95": 71.0
  },
  "mode": "bm25",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
