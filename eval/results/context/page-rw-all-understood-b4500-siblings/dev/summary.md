# context: page-rw-all-understood-b4500-siblings (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| context_hit | 0.680 | 0.590 to 0.770 |
| context_recall | 0.657 | 0.565 to 0.747 |

## By question type

| Question type | Questions | context_hit | context_recall |
|---|---|---|---|
| domain-relevant | 34 | 0.588 (0.41 to 0.76) | 0.549 (0.39 to 0.71) |
| metrics-generated | 33 | 0.909 (0.79 to 1.00) | 0.879 (0.77 to 0.97) |
| novel-generated | 33 | 0.545 (0.36 to 0.73) | 0.545 (0.36 to 0.73) |

## System

```json
{
  "budget_tokens": 4500,
  "collection": "fb_page_bge-small",
  "mean_sources": 13.17,
  "mean_tokens": 4461,
  "retrieval": "understood filings, three rewrites, fused dense search",
  "split_page_parts": true
}
```
