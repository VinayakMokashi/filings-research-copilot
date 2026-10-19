# retrieval: page_bge-small-dense-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 16:49 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.613 | 0.523 to 0.703 |
| recall@10 | 0.722 | 0.633 to 0.805 |
| recall@20 | 0.787 | 0.707 to 0.862 |
| hit@5 | 0.660 | 0.570 to 0.750 |
| hit@10 | 0.740 | 0.650 to 0.820 |
| hit@20 | 0.800 | 0.720 to 0.880 |
| mrr@10 | 0.476 | 0.394 to 0.559 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.480 (0.32 to 0.64) | 0.608 (0.45 to 0.76) | 0.740 (0.59 to 0.87) | 0.559 (0.38 to 0.74) | 0.647 (0.47 to 0.79) | 0.765 (0.62 to 0.88) | 0.340 (0.22 to 0.47) |
| metrics-generated | 33 | 0.848 (0.73 to 0.94) | 0.924 (0.83 to 1.00) | 0.924 (0.83 to 1.00) | 0.909 (0.79 to 1.00) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.808 (0.68 to 0.92) |
| novel-generated | 33 | 0.515 (0.33 to 0.70) | 0.636 (0.45 to 0.79) | 0.697 (0.55 to 0.85) | 0.515 (0.33 to 0.70) | 0.636 (0.45 to 0.79) | 0.697 (0.55 to 0.85) | 0.284 (0.18 to 0.40) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 4345.0,
    "p50": 4520.1,
    "p95": 7888.1
  },
  "mode": "dense",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "rewrite": {
    "cache": {
      "hits": 300,
      "misses": 0
    },
    "fusion": "RRF, k = 60, over the question and every rewrite",
    "kinds": [
      "multi",
      "hyde",
      "decompose"
    ],
    "latency_ms_p50": 4239.1,
    "model": "groq/qwen/qwen3.8-27b",
    "prompt_version": "1",
    "tokens": 62688
  },
  "setting": "understood",
  "strategy": "page"
}
```
