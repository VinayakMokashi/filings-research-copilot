# retrieval: tokens-480_bge-small-hybrid-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.125 | 0.065 to 0.190 |
| recall@10 | 0.210 | 0.135 to 0.290 |
| recall@20 | 0.350 | 0.260 to 0.445 |
| hit@5 | 0.140 | 0.080 to 0.210 |
| hit@10 | 0.240 | 0.160 to 0.330 |
| hit@20 | 0.380 | 0.290 to 0.480 |
| mrr@10 | 0.118 | 0.066 to 0.175 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.074 (0.00 to 0.16) | 0.147 (0.04 to 0.26) | 0.221 (0.10 to 0.35) | 0.088 (0.00 to 0.21) | 0.176 (0.06 to 0.32) | 0.265 (0.12 to 0.41) | 0.101 (0.02 to 0.21) |
| metrics-generated | 33 | 0.091 (0.02 to 0.18) | 0.182 (0.08 to 0.30) | 0.379 (0.23 to 0.55) | 0.121 (0.03 to 0.24) | 0.242 (0.09 to 0.39) | 0.424 (0.27 to 0.61) | 0.103 (0.03 to 0.20) |
| novel-generated | 33 | 0.212 (0.09 to 0.36) | 0.303 (0.15 to 0.45) | 0.455 (0.27 to 0.64) | 0.212 (0.09 to 0.36) | 0.303 (0.15 to 0.45) | 0.455 (0.27 to 0.64) | 0.151 (0.06 to 0.26) |

## System

```json
{
  "candidates_per_ranking": 50,
  "collection": "fb_tokens-480_bge-small",
  "dense_model": "BAAI/bge-small-en-v1.5",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 65.3,
    "p50": 61.4,
    "p95": 92.3
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "setting": "corpus",
  "strategy": "tokens-480"
}
```
