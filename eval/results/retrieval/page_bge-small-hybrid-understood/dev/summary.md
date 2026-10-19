# retrieval: page_bge-small-hybrid-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 15:55 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.405 | 0.315 to 0.500 |
| recall@10 | 0.525 | 0.430 to 0.620 |
| recall@20 | 0.630 | 0.540 to 0.720 |
| hit@5 | 0.440 | 0.340 to 0.540 |
| hit@10 | 0.560 | 0.460 to 0.660 |
| hit@20 | 0.660 | 0.570 to 0.750 |
| mrr@10 | 0.274 | 0.207 to 0.344 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.31) | 0.279 (0.15 to 0.43) | 0.412 (0.25 to 0.57) | 0.206 (0.09 to 0.35) | 0.324 (0.18 to 0.50) | 0.441 (0.26 to 0.62) | 0.143 (0.06 to 0.25) |
| metrics-generated | 33 | 0.561 (0.41 to 0.71) | 0.697 (0.56 to 0.83) | 0.742 (0.59 to 0.88) | 0.636 (0.48 to 0.79) | 0.758 (0.61 to 0.91) | 0.788 (0.64 to 0.91) | 0.352 (0.24 to 0.47) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.606 (0.42 to 0.76) | 0.742 (0.59 to 0.88) | 0.485 (0.30 to 0.67) | 0.606 (0.42 to 0.76) | 0.758 (0.61 to 0.91) | 0.330 (0.20 to 0.47) |

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
    "mean": 48.5,
    "p50": 47.0,
    "p95": 64.4
  },
  "mode": "hybrid",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "rrf_k": 60,
  "setting": "understood",
  "strategy": "page"
}
```
