# retrieval: tokens-480_bge-small-dense-rerank-minilm-l6-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 14:58 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.390 | 0.300 to 0.485 |
| recall@10 | 0.510 | 0.415 to 0.605 |
| recall@20 | 0.678 | 0.587 to 0.765 |
| hit@5 | 0.440 | 0.340 to 0.540 |
| hit@10 | 0.550 | 0.450 to 0.650 |
| hit@20 | 0.700 | 0.610 to 0.790 |
| mrr@10 | 0.264 | 0.199 to 0.337 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.147 (0.04 to 0.26) | 0.206 (0.09 to 0.34) | 0.377 (0.23 to 0.54) | 0.176 (0.06 to 0.32) | 0.235 (0.09 to 0.38) | 0.412 (0.26 to 0.59) | 0.063 (0.02 to 0.11) |
| metrics-generated | 33 | 0.424 (0.29 to 0.58) | 0.576 (0.42 to 0.73) | 0.848 (0.73 to 0.95) | 0.545 (0.36 to 0.73) | 0.667 (0.48 to 0.82) | 0.879 (0.76 to 0.97) | 0.329 (0.21 to 0.45) |
| novel-generated | 33 | 0.606 (0.42 to 0.79) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.606 (0.42 to 0.79) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.408 (0.28 to 0.55) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 1,
  "late_chunking": false,
  "latency_ms": {
    "mean": 7744.8,
    "p50": 7281.6,
    "p95": 10349.4
  },
  "mode": "dense",
  "rerank_top": 30,
  "reranker": "Xenova/ms-marco-MiniLM-L-6-v2",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
