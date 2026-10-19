# retrieval: page_bge-small-dense-rw-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 16:48 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.565 | 0.470 to 0.660 |
| recall@10 | 0.662 | 0.572 to 0.750 |
| recall@20 | 0.762 | 0.680 to 0.840 |
| hit@5 | 0.590 | 0.490 to 0.690 |
| hit@10 | 0.690 | 0.600 to 0.780 |
| hit@20 | 0.780 | 0.700 to 0.860 |
| mrr@10 | 0.415 | 0.337 to 0.497 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.441 (0.28 to 0.60) | 0.593 (0.43 to 0.74) | 0.681 (0.52 to 0.82) | 0.471 (0.29 to 0.65) | 0.647 (0.47 to 0.79) | 0.706 (0.56 to 0.85) | 0.311 (0.20 to 0.43) |
| metrics-generated | 33 | 0.803 (0.67 to 0.92) | 0.879 (0.77 to 0.97) | 0.909 (0.80 to 0.98) | 0.848 (0.73 to 0.97) | 0.909 (0.79 to 1.00) | 0.939 (0.85 to 1.00) | 0.667 (0.53 to 0.79) |
| novel-generated | 33 | 0.455 (0.27 to 0.64) | 0.515 (0.33 to 0.70) | 0.697 (0.55 to 0.85) | 0.455 (0.27 to 0.64) | 0.515 (0.33 to 0.70) | 0.697 (0.55 to 0.85) | 0.270 (0.16 to 0.39) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 401.4,
    "p50": 360.7,
    "p95": 570.5
  },
  "mode": "dense",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "rewrite": {
    "cache": {
      "hits": 2,
      "misses": 98
    },
    "fusion": "RRF, k = 60, over the question and every rewrite",
    "kinds": [
      "decompose"
    ],
    "latency_ms_p50": 262.1,
    "model": "groq/qwen/qwen3.8-27b",
    "prompt_version": "1",
    "tokens": 17106
  },
  "setting": "understood",
  "strategy": "page"
}
```
