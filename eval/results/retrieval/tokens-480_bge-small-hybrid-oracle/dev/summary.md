# retrieval: tokens-480_bge-small-hybrid-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-18 00:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.385 | 0.295 to 0.480 |
| recall@10 | 0.540 | 0.445 to 0.635 |
| recall@20 | 0.645 | 0.555 to 0.730 |
| hit@5 | 0.410 | 0.310 to 0.510 |
| hit@10 | 0.570 | 0.470 to 0.660 |
| hit@20 | 0.680 | 0.590 to 0.770 |
| mrr@10 | 0.277 | 0.210 to 0.349 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.176 (0.06 to 0.31) | 0.235 (0.10 to 0.38) | 0.324 (0.18 to 0.47) | 0.206 (0.09 to 0.35) | 0.265 (0.12 to 0.41) | 0.382 (0.23 to 0.56) | 0.141 (0.05 to 0.25) |
| metrics-generated | 33 | 0.470 (0.30 to 0.64) | 0.636 (0.48 to 0.79) | 0.773 (0.64 to 0.89) | 0.515 (0.33 to 0.70) | 0.697 (0.55 to 0.85) | 0.818 (0.67 to 0.94) | 0.362 (0.24 to 0.49) |
| novel-generated | 33 | 0.515 (0.33 to 0.70) | 0.758 (0.61 to 0.91) | 0.848 (0.73 to 0.97) | 0.515 (0.33 to 0.70) | 0.758 (0.61 to 0.91) | 0.848 (0.73 to 0.97) | 0.334 (0.22 to 0.46) |

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
    "mean": 55.0,
    "p50": 53.0,
    "p95": 83.3
  },
  "mode": "hybrid",
  "rrf_k": 60,
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
