# retrieval: page_bge-small-bm25-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:27 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.305 | 0.220 to 0.395 |
| recall@10 | 0.430 | 0.335 to 0.530 |
| recall@20 | 0.565 | 0.475 to 0.660 |
| hit@5 | 0.310 | 0.220 to 0.400 |
| hit@10 | 0.450 | 0.350 to 0.550 |
| hit@20 | 0.600 | 0.500 to 0.700 |
| mrr@10 | 0.243 | 0.172 to 0.317 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.32) | 0.206 (0.09 to 0.35) | 0.338 (0.19 to 0.50) | 0.176 (0.06 to 0.32) | 0.206 (0.09 to 0.35) | 0.353 (0.21 to 0.53) | 0.137 (0.04 to 0.25) |
| metrics-generated | 33 | 0.152 (0.03 to 0.27) | 0.288 (0.15 to 0.44) | 0.530 (0.38 to 0.68) | 0.152 (0.03 to 0.27) | 0.333 (0.18 to 0.48) | 0.606 (0.45 to 0.76) | 0.117 (0.04 to 0.21) |
| novel-generated | 33 | 0.591 (0.42 to 0.76) | 0.803 (0.67 to 0.92) | 0.833 (0.70 to 0.94) | 0.606 (0.45 to 0.76) | 0.818 (0.67 to 0.94) | 0.848 (0.73 to 0.97) | 0.478 (0.34 to 0.62) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 18.0,
    "p50": 17.8,
    "p95": 29.0
  },
  "mode": "bm25",
  "setting": "oracle",
  "strategy": "page"
}
```
