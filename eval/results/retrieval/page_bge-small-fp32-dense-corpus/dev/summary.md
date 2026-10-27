# retrieval: page_bge-small-fp32-dense-corpus (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 20:33 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.305 | 0.220 to 0.395 |
| recall@10 | 0.415 | 0.325 to 0.510 |
| recall@20 | 0.495 | 0.400 to 0.590 |
| hit@5 | 0.340 | 0.250 to 0.440 |
| hit@10 | 0.460 | 0.360 to 0.560 |
| hit@20 | 0.520 | 0.420 to 0.620 |
| mrr@10 | 0.231 | 0.166 to 0.302 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.191 (0.07 to 0.32) | 0.250 (0.12 to 0.40) | 0.294 (0.16 to 0.44) | 0.235 (0.09 to 0.38) | 0.294 (0.15 to 0.44) | 0.324 (0.18 to 0.50) | 0.133 (0.05 to 0.23) |
| metrics-generated | 33 | 0.455 (0.30 to 0.61) | 0.576 (0.42 to 0.73) | 0.712 (0.56 to 0.85) | 0.515 (0.33 to 0.70) | 0.667 (0.52 to 0.82) | 0.758 (0.61 to 0.91) | 0.344 (0.22 to 0.48) |
| novel-generated | 33 | 0.273 (0.12 to 0.42) | 0.424 (0.27 to 0.61) | 0.485 (0.30 to 0.67) | 0.273 (0.12 to 0.42) | 0.424 (0.27 to 0.61) | 0.485 (0.30 to 0.67) | 0.219 (0.11 to 0.35) |

## System

```json
{
  "collection": "fb_page_bge-small-fp32",
  "dense_model": "BAAI/bge-small-en-v1.5, fp32 ONNX export",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 33.4,
    "p50": 31.3,
    "p95": 49.1
  },
  "mode": "dense",
  "setting": "corpus",
  "strategy": "page"
}
```
