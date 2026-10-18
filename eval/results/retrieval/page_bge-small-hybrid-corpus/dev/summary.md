# retrieval: page_bge-small-hybrid-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:28 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.215 | 0.140 to 0.295 |
| recall@10 | 0.315 | 0.230 to 0.405 |
| recall@20 | 0.440 | 0.345 to 0.535 |
| hit@5 | 0.230 | 0.150 to 0.310 |
| hit@10 | 0.340 | 0.250 to 0.430 |
| hit@20 | 0.470 | 0.370 to 0.570 |
| mrr@10 | 0.150 | 0.095 to 0.212 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.132 (0.03 to 0.25) | 0.206 (0.09 to 0.34) | 0.265 (0.13 to 0.41) | 0.147 (0.03 to 0.26) | 0.235 (0.12 to 0.38) | 0.294 (0.15 to 0.44) | 0.093 (0.02 to 0.18) |
| metrics-generated | 33 | 0.182 (0.06 to 0.32) | 0.348 (0.20 to 0.52) | 0.545 (0.38 to 0.71) | 0.212 (0.09 to 0.36) | 0.394 (0.24 to 0.58) | 0.606 (0.42 to 0.76) | 0.141 (0.06 to 0.24) |
| novel-generated | 33 | 0.333 (0.18 to 0.48) | 0.394 (0.24 to 0.55) | 0.515 (0.33 to 0.67) | 0.333 (0.18 to 0.48) | 0.394 (0.24 to 0.55) | 0.515 (0.33 to 0.67) | 0.218 (0.10 to 0.35) |

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
    "mean": 60.7,
    "p50": 57.3,
    "p95": 78.8
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "setting": "corpus",
  "strategy": "page"
}
```
