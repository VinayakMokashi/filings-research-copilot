# retrieval: page_bge-small-fp32-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 20:33 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.530 | 0.435 to 0.625 |
| recall@10 | 0.630 | 0.535 to 0.720 |
| recall@20 | 0.760 | 0.675 to 0.840 |
| hit@5 | 0.570 | 0.470 to 0.670 |
| hit@10 | 0.650 | 0.560 to 0.740 |
| hit@20 | 0.770 | 0.680 to 0.850 |
| mrr@10 | 0.423 | 0.342 to 0.506 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.279 (0.15 to 0.43) | 0.353 (0.21 to 0.51) | 0.574 (0.41 to 0.74) | 0.324 (0.18 to 0.50) | 0.382 (0.24 to 0.56) | 0.588 (0.41 to 0.74) | 0.229 (0.12 to 0.36) |
| metrics-generated | 33 | 0.712 (0.58 to 0.85) | 0.788 (0.65 to 0.91) | 0.894 (0.79 to 0.98) | 0.788 (0.64 to 0.91) | 0.818 (0.67 to 0.94) | 0.909 (0.79 to 1.00) | 0.604 (0.46 to 0.74) |
| novel-generated | 33 | 0.606 (0.45 to 0.76) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.606 (0.45 to 0.76) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.440 (0.31 to 0.58) |

## System

```json
{
  "collection": "fb_page_bge-small-fp32",
  "dense_model": "BAAI/bge-small-en-v1.5, fp32 ONNX export",
  "fetched_chunks": 60,
  "index_documents": 84,
  "late_chunking": false,
  "latency_ms": {
    "mean": 34.8,
    "p50": 32.3,
    "p95": 58.4
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "page"
}
```
