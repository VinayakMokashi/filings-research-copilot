# retrieval: tokens-480_bge-small-bm25-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.090 | 0.040 to 0.150 |
| recall@10 | 0.155 | 0.090 to 0.225 |
| recall@20 | 0.210 | 0.135 to 0.290 |
| hit@5 | 0.090 | 0.040 to 0.150 |
| hit@10 | 0.170 | 0.100 to 0.250 |
| hit@20 | 0.230 | 0.150 to 0.310 |
| mrr@10 | 0.081 | 0.037 to 0.131 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.088 (0.00 to 0.21) | 0.088 (0.00 to 0.21) | 0.132 (0.03 to 0.25) | 0.088 (0.00 to 0.21) | 0.088 (0.00 to 0.21) | 0.147 (0.03 to 0.26) | 0.088 (0.00 to 0.21) |
| metrics-generated | 33 | 0.030 (0.00 to 0.09) | 0.106 (0.03 to 0.21) | 0.136 (0.05 to 0.26) | 0.030 (0.00 to 0.09) | 0.152 (0.03 to 0.27) | 0.182 (0.06 to 0.33) | 0.047 (0.01 to 0.12) |
| novel-generated | 33 | 0.152 (0.03 to 0.27) | 0.273 (0.12 to 0.42) | 0.364 (0.21 to 0.52) | 0.152 (0.03 to 0.27) | 0.273 (0.12 to 0.42) | 0.364 (0.21 to 0.52) | 0.107 (0.03 to 0.20) |

## System

```json
{
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 22.7,
    "p50": 20.4,
    "p95": 40.2
  },
  "mode": "bm25",
  "setting": "corpus",
  "strategy": "tokens-480"
}
```
