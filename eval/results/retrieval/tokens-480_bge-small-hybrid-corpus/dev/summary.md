# retrieval: tokens-480_bge-small-hybrid-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 15:35 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.130 | 0.070 to 0.195 |
| recall@10 | 0.210 | 0.135 to 0.290 |
| recall@20 | 0.355 | 0.265 to 0.450 |
| hit@5 | 0.150 | 0.080 to 0.220 |
| hit@10 | 0.240 | 0.160 to 0.330 |
| hit@20 | 0.390 | 0.300 to 0.490 |
| mrr@10 | 0.126 | 0.073 to 0.187 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.074 (0.00 to 0.16) | 0.147 (0.04 to 0.26) | 0.221 (0.10 to 0.35) | 0.088 (0.00 to 0.21) | 0.176 (0.06 to 0.32) | 0.265 (0.12 to 0.41) | 0.102 (0.02 to 0.21) |
| metrics-generated | 33 | 0.106 (0.03 to 0.21) | 0.182 (0.08 to 0.30) | 0.394 (0.24 to 0.56) | 0.152 (0.03 to 0.27) | 0.242 (0.09 to 0.39) | 0.455 (0.27 to 0.64) | 0.105 (0.03 to 0.20) |
| novel-generated | 33 | 0.212 (0.09 to 0.36) | 0.303 (0.15 to 0.45) | 0.455 (0.27 to 0.64) | 0.212 (0.09 to 0.36) | 0.303 (0.15 to 0.45) | 0.455 (0.27 to 0.64) | 0.174 (0.07 to 0.29) |

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
    "mean": 276.2,
    "p50": 249.3,
    "p95": 501.5
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "setting": "corpus",
  "strategy": "tokens-480"
}
```
