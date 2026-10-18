# retrieval: page_bge-small-bm25-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:27 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.125 | 0.065 to 0.190 |
| recall@10 | 0.185 | 0.115 to 0.260 |
| recall@20 | 0.245 | 0.160 to 0.330 |
| hit@5 | 0.130 | 0.070 to 0.200 |
| hit@10 | 0.190 | 0.120 to 0.270 |
| hit@20 | 0.250 | 0.170 to 0.340 |
| mrr@10 | 0.100 | 0.052 to 0.155 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.088 (0.00 to 0.21) | 0.088 (0.00 to 0.21) | 0.191 (0.07 to 0.32) | 0.088 (0.00 to 0.21) | 0.088 (0.00 to 0.21) | 0.206 (0.09 to 0.35) | 0.088 (0.00 to 0.21) |
| metrics-generated | 33 | 0.045 (0.00 to 0.12) | 0.076 (0.00 to 0.17) | 0.121 (0.03 to 0.24) | 0.061 (0.00 to 0.15) | 0.091 (0.00 to 0.21) | 0.121 (0.03 to 0.24) | 0.043 (0.00 to 0.11) |
| novel-generated | 33 | 0.242 (0.09 to 0.39) | 0.394 (0.24 to 0.55) | 0.424 (0.24 to 0.58) | 0.242 (0.09 to 0.39) | 0.394 (0.24 to 0.55) | 0.424 (0.24 to 0.58) | 0.169 (0.07 to 0.28) |

## System

```json
{
  "collection": "fb_page_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 19.2,
    "p50": 18.3,
    "p95": 25.4
  },
  "mode": "bm25",
  "setting": "corpus",
  "strategy": "page"
}
```
