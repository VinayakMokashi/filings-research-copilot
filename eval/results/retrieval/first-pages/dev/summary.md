# retrieval: first-pages (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-16 20:12 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| recall@5 | 0.140 | 0.080 to 0.210 |
| recall@10 | 0.197 | 0.123 to 0.277 |
| recall@20 | 0.290 | 0.200 to 0.380 |
| hit@5 | 0.140 | 0.080 to 0.210 |
| hit@10 | 0.200 | 0.130 to 0.280 |
| hit@20 | 0.290 | 0.200 to 0.380 |
| mrr@10 | 0.075 | 0.041 to 0.117 |

## By question type

| Question type | Questions | recall@5 | recall@10 | recall@20 | hit@5 | hit@10 | hit@20 | mrr@10 |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.147 (0.03 to 0.26) | 0.167 (0.06 to 0.29) | 0.176 (0.06 to 0.32) | 0.147 (0.03 to 0.26) | 0.176 (0.06 to 0.32) | 0.176 (0.06 to 0.32) | 0.084 (0.02 to 0.17) |
| metrics-generated | 33 | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) |
| novel-generated | 33 | 0.273 (0.12 to 0.42) | 0.424 (0.27 to 0.61) | 0.697 (0.52 to 0.85) | 0.273 (0.12 to 0.42) | 0.424 (0.27 to 0.61) | 0.697 (0.52 to 0.85) | 0.142 (0.07 to 0.22) |

## System

```json
{
  "baseline": "first-pages",
  "document": "oracle",
  "pages": 20
}
```
