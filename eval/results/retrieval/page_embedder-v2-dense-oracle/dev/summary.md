# retrieval: page_embedder-v2-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 21:20 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.475 | 0.380 to 0.565 |
| recall@10 | 0.645 | 0.555 to 0.735 |
| recall@20 | 0.772 | 0.690 to 0.848 |
| hit@5 | 0.520 | 0.420 to 0.620 |
| hit@10 | 0.680 | 0.590 to 0.770 |
| hit@20 | 0.800 | 0.720 to 0.880 |
| mrr@10 | 0.369 | 0.293 to 0.448 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.309 (0.16 to 0.46) | 0.412 (0.25 to 0.57) | 0.623 (0.46 to 0.77) | 0.353 (0.21 to 0.53) | 0.441 (0.26 to 0.62) | 0.676 (0.50 to 0.82) | 0.192 (0.10 to 0.30) |
| metrics-generated | 33 | 0.591 (0.44 to 0.74) | 0.712 (0.58 to 0.85) | 0.833 (0.70 to 0.94) | 0.667 (0.52 to 0.82) | 0.788 (0.64 to 0.91) | 0.848 (0.73 to 0.97) | 0.531 (0.39 to 0.68) |
| novel-generated | 33 | 0.530 (0.36 to 0.70) | 0.818 (0.67 to 0.94) | 0.864 (0.74 to 0.97) | 0.545 (0.36 to 0.70) | 0.818 (0.67 to 0.94) | 0.879 (0.76 to 0.97) | 0.391 (0.27 to 0.52) |

## System

```json
{
  "collection": "fb_page_embedder-v2",
  "dense_model": "embedder-v2: bge-small-en-v1.5 fine-tuned on filings, with negatives from other companies",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 33.6,
    "p50": 30.4,
    "p95": 54.0
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "page"
}
```
