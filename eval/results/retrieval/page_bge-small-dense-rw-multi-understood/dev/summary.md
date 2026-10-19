# retrieval: page_bge-small-dense-rw-multi-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 16:32 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.548 | 0.452 to 0.643 |
| recall@10 | 0.682 | 0.590 to 0.768 |
| recall@20 | 0.782 | 0.700 to 0.858 |
| hit@5 | 0.570 | 0.470 to 0.670 |
| hit@10 | 0.700 | 0.610 to 0.790 |
| hit@20 | 0.790 | 0.710 to 0.870 |
| mrr@10 | 0.454 | 0.368 to 0.540 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.407 (0.25 to 0.57) | 0.578 (0.42 to 0.74) | 0.740 (0.59 to 0.87) | 0.441 (0.26 to 0.62) | 0.618 (0.44 to 0.76) | 0.765 (0.62 to 0.91) | 0.313 (0.19 to 0.44) |
| metrics-generated | 33 | 0.788 (0.65 to 0.91) | 0.924 (0.83 to 1.00) | 0.939 (0.85 to 1.00) | 0.818 (0.67 to 0.94) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.778 (0.64 to 0.90) |
| novel-generated | 33 | 0.455 (0.30 to 0.64) | 0.545 (0.39 to 0.70) | 0.667 (0.52 to 0.82) | 0.455 (0.30 to 0.64) | 0.545 (0.39 to 0.70) | 0.667 (0.52 to 0.82) | 0.275 (0.16 to 0.40) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 470.1,
    "p50": 417.6,
    "p95": 616.3
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
      "multi"
    ],
    "latency_ms_p50": 297.7,
    "model": "groq/qwen/qwen3.8-27b",
    "prompt_version": "1",
    "tokens": 20720
  },
  "setting": "understood",
  "strategy": "page"
}
```
