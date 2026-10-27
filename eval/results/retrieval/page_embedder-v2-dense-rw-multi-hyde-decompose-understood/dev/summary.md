# retrieval: page_embedder-v2-dense-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 21:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.630 | 0.535 to 0.725 |
| recall@10 | 0.742 | 0.657 to 0.823 |
| recall@20 | 0.817 | 0.742 to 0.888 |
| hit@5 | 0.640 | 0.540 to 0.730 |
| hit@10 | 0.770 | 0.690 to 0.850 |
| hit@20 | 0.840 | 0.770 to 0.910 |
| mrr@10 | 0.486 | 0.405 to 0.569 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.471 (0.29 to 0.65) | 0.637 (0.48 to 0.78) | 0.681 (0.53 to 0.82) | 0.471 (0.29 to 0.65) | 0.706 (0.53 to 0.85) | 0.735 (0.59 to 0.88) | 0.366 (0.24 to 0.49) |
| metrics-generated | 33 | 0.879 (0.77 to 0.97) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.909 (0.79 to 1.00) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.778 (0.66 to 0.89) |
| novel-generated | 33 | 0.545 (0.36 to 0.73) | 0.652 (0.48 to 0.80) | 0.833 (0.70 to 0.94) | 0.545 (0.36 to 0.73) | 0.667 (0.52 to 0.82) | 0.848 (0.73 to 0.97) | 0.319 (0.21 to 0.44) |

## System

```json
{
  "collection": "fb_page_embedder-v2",
  "dense_model": "embedder-v2: bge-small-en-v1.5 fine-tuned on filings, with negatives from other companies",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 4341.8,
    "p50": 4494.5,
    "p95": 7873.7
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
