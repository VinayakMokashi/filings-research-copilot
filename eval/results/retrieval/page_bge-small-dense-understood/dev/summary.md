# retrieval: page_bge-small-dense-understood (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 15:55 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.470 | 0.375 to 0.565 |
| recall@10 | 0.570 | 0.475 to 0.665 |
| recall@20 | 0.690 | 0.600 to 0.775 |
| hit@5 | 0.510 | 0.410 to 0.610 |
| hit@10 | 0.590 | 0.490 to 0.690 |
| hit@20 | 0.700 | 0.610 to 0.790 |
| mrr@10 | 0.381 | 0.301 to 0.466 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.221 (0.10 to 0.35) | 0.324 (0.18 to 0.47) | 0.544 (0.38 to 0.71) | 0.265 (0.12 to 0.41) | 0.353 (0.21 to 0.53) | 0.559 (0.38 to 0.71) | 0.203 (0.10 to 0.32) |
| metrics-generated | 33 | 0.712 (0.58 to 0.85) | 0.788 (0.65 to 0.91) | 0.864 (0.74 to 0.97) | 0.788 (0.64 to 0.91) | 0.818 (0.67 to 0.94) | 0.879 (0.76 to 0.97) | 0.595 (0.45 to 0.73) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.606 (0.42 to 0.76) | 0.667 (0.52 to 0.82) | 0.485 (0.30 to 0.67) | 0.606 (0.42 to 0.76) | 0.667 (0.52 to 0.82) | 0.351 (0.22 to 0.49) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 31.5,
    "p50": 30.1,
    "p95": 42.4
  },
  "mode": "dense",
  "query_understanding": {
    "mean_filings": 1.49,
    "own_filing_included": 98,
    "resolved": 98
  },
  "setting": "understood",
  "strategy": "page"
}
```
