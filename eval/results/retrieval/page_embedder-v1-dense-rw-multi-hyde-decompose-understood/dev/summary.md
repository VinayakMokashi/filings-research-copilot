# retrieval: page_embedder-v1-dense-rw-multi-hyde-decompose-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 20:35 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.670 | 0.580 to 0.760 |
| recall@10 | 0.747 | 0.663 to 0.828 |
| recall@20 | 0.852 | 0.783 to 0.917 |
| hit@5 | 0.690 | 0.600 to 0.780 |
| hit@10 | 0.780 | 0.700 to 0.860 |
| hit@20 | 0.870 | 0.800 to 0.930 |
| mrr@10 | 0.514 | 0.431 to 0.598 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.603 (0.44 to 0.76) | 0.637 (0.48 to 0.78) | 0.770 (0.63 to 0.89) | 0.618 (0.44 to 0.76) | 0.706 (0.53 to 0.85) | 0.824 (0.68 to 0.94) | 0.415 (0.28 to 0.55) |
| metrics-generated | 33 | 0.864 (0.74 to 0.95) | 0.924 (0.83 to 1.00) | 0.939 (0.85 to 1.00) | 0.909 (0.79 to 1.00) | 0.939 (0.85 to 1.00) | 0.939 (0.85 to 1.00) | 0.761 (0.64 to 0.88) |
| novel-generated | 33 | 0.545 (0.36 to 0.73) | 0.682 (0.52 to 0.83) | 0.848 (0.73 to 0.97) | 0.545 (0.36 to 0.73) | 0.697 (0.55 to 0.85) | 0.848 (0.73 to 0.97) | 0.368 (0.24 to 0.51) |

## System

```json
{
  "collection": "fb_page_embedder-v1",
  "dense_model": "embedder-v1: bge-small-en-v1.5 fine-tuned on filings",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 4337.1,
    "p50": 4491.9,
    "p95": 7871.0
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
