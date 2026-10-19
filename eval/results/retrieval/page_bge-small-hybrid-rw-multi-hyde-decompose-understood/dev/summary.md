# retrieval: page_bge-small-hybrid-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 16:51 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.583 | 0.487 to 0.678 |
| recall@10 | 0.697 | 0.607 to 0.782 |
| recall@20 | 0.805 | 0.727 to 0.877 |
| hit@5 | 0.620 | 0.520 to 0.720 |
| hit@10 | 0.730 | 0.640 to 0.820 |
| hit@20 | 0.830 | 0.750 to 0.900 |
| mrr@10 | 0.436 | 0.356 to 0.517 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.422 (0.26 to 0.58) | 0.564 (0.41 to 0.72) | 0.735 (0.59 to 0.86) | 0.471 (0.29 to 0.65) | 0.618 (0.44 to 0.76) | 0.794 (0.65 to 0.91) | 0.337 (0.21 to 0.48) |
| metrics-generated | 33 | 0.788 (0.65 to 0.91) | 0.894 (0.79 to 0.97) | 0.924 (0.83 to 1.00) | 0.848 (0.73 to 0.97) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.629 (0.50 to 0.76) |
| novel-generated | 33 | 0.545 (0.36 to 0.70) | 0.636 (0.48 to 0.79) | 0.758 (0.61 to 0.88) | 0.545 (0.36 to 0.70) | 0.636 (0.48 to 0.79) | 0.758 (0.61 to 0.88) | 0.343 (0.22 to 0.48) |

## System

```json
{
  "candidates_per_ranking": 50,
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 4489.9,
    "p50": 4659.2,
    "p95": 8038.0
  },
  "mode": "hybrid",
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
  "rrf_k": 60,
  "setting": "understood",
  "strategy": "page"
}
```
