# retrieval: page_embedder-v1-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 20:34 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.495 | 0.400 to 0.590 |
| recall@10 | 0.660 | 0.570 to 0.745 |
| recall@20 | 0.778 | 0.698 to 0.855 |
| hit@5 | 0.540 | 0.440 to 0.640 |
| hit@10 | 0.700 | 0.610 to 0.790 |
| hit@20 | 0.800 | 0.720 to 0.880 |
| mrr@10 | 0.373 | 0.299 to 0.449 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.338 (0.19 to 0.49) | 0.412 (0.25 to 0.57) | 0.657 (0.50 to 0.80) | 0.382 (0.24 to 0.56) | 0.441 (0.26 to 0.62) | 0.676 (0.50 to 0.82) | 0.223 (0.12 to 0.34) |
| metrics-generated | 33 | 0.591 (0.44 to 0.74) | 0.742 (0.61 to 0.86) | 0.818 (0.68 to 0.94) | 0.667 (0.52 to 0.82) | 0.818 (0.67 to 0.94) | 0.848 (0.73 to 0.97) | 0.501 (0.37 to 0.64) |
| novel-generated | 33 | 0.561 (0.39 to 0.73) | 0.833 (0.70 to 0.94) | 0.864 (0.74 to 0.97) | 0.576 (0.39 to 0.73) | 0.848 (0.73 to 0.97) | 0.879 (0.76 to 0.97) | 0.400 (0.28 to 0.52) |

## System

```json
{
  "collection": "fb_page_embedder-v1",
  "dense_model": "embedder-v1: bge-small-en-v1.5 fine-tuned on filings",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 31.2,
    "p50": 28.3,
    "p95": 48.5
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "page"
}
```
