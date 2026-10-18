# retrieval: tokens-480_jina-small-late-dense-oracle (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-17 20:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.453 | 0.362 to 0.550 |
| recall@10 | 0.613 | 0.520 to 0.705 |
| recall@20 | 0.770 | 0.690 to 0.845 |
| hit@5 | 0.490 | 0.400 to 0.590 |
| hit@10 | 0.650 | 0.560 to 0.740 |
| hit@20 | 0.790 | 0.710 to 0.870 |
| mrr@10 | 0.328 | 0.257 to 0.403 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.186 (0.07 to 0.31) | 0.377 (0.23 to 0.53) | 0.588 (0.43 to 0.75) | 0.235 (0.09 to 0.38) | 0.441 (0.26 to 0.62) | 0.618 (0.44 to 0.76) | 0.164 (0.08 to 0.27) |
| metrics-generated | 33 | 0.606 (0.45 to 0.76) | 0.727 (0.58 to 0.86) | 0.909 (0.82 to 0.98) | 0.667 (0.48 to 0.82) | 0.758 (0.61 to 0.88) | 0.939 (0.85 to 1.00) | 0.458 (0.33 to 0.59) |
| novel-generated | 33 | 0.576 (0.39 to 0.73) | 0.742 (0.59 to 0.88) | 0.818 (0.67 to 0.94) | 0.576 (0.39 to 0.73) | 0.758 (0.61 to 0.91) | 0.818 (0.67 to 0.94) | 0.367 (0.25 to 0.49) |

## System

```json
{
  "collection": "fb_tokens-480_jina-small-late",
  "dense_model": "jinaai/jina-embeddings-v2-small-en",
  "fetched_chunks": 60,
  "index_documents": 58,
  "late_chunking": true,
  "latency_ms": {
    "mean": 29.9,
    "p50": 27.6,
    "p95": 44.4
  },
  "mode": "dense",
  "setting": "oracle",
  "strategy": "tokens-480"
}
```
