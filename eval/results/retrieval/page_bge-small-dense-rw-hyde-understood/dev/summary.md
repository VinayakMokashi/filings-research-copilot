# retrieval: page_bge-small-dense-rw-hyde-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 16:43 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.545 | 0.450 to 0.640 |
| recall@10 | 0.682 | 0.592 to 0.770 |
| recall@20 | 0.817 | 0.742 to 0.885 |
| hit@5 | 0.570 | 0.470 to 0.670 |
| hit@10 | 0.710 | 0.620 to 0.800 |
| hit@20 | 0.850 | 0.780 to 0.920 |
| mrr@10 | 0.388 | 0.313 to 0.465 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.353 (0.21 to 0.51) | 0.446 (0.28 to 0.61) | 0.667 (0.51 to 0.81) | 0.382 (0.24 to 0.56) | 0.471 (0.29 to 0.65) | 0.706 (0.56 to 0.85) | 0.210 (0.11 to 0.32) |
| metrics-generated | 33 | 0.803 (0.67 to 0.92) | 0.894 (0.79 to 0.97) | 0.939 (0.86 to 1.00) | 0.848 (0.73 to 0.97) | 0.939 (0.85 to 1.00) | 0.970 (0.91 to 1.00) | 0.586 (0.46 to 0.71) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.712 (0.56 to 0.86) | 0.848 (0.73 to 0.95) | 0.485 (0.30 to 0.67) | 0.727 (0.58 to 0.88) | 0.879 (0.76 to 0.97) | 0.373 (0.25 to 0.51) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 3513.0,
    "p50": 3662.8,
    "p95": 7191.8
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
      "hyde"
    ],
    "latency_ms_p50": 3601.9,
    "model": "groq/qwen/qwen3.8-27b",
    "prompt_version": "1",
    "tokens": 24862
  },
  "setting": "understood",
  "strategy": "page"
}
```
