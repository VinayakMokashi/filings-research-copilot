# context: page-rw-all-understood-b3000-siblings (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| context_hit | 0.610 | 0.510 to 0.700 |
| context_recall | 0.580 | 0.485 to 0.675 |

## By question type

| Question type | Questions | context_hit | context_recall |
|---|---|---|---|
| domain-relevant | 34 | 0.500 (0.32 to 0.68) | 0.456 (0.29 to 0.62) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.833 (0.71 to 0.94) |
| novel-generated | 33 | 0.455 (0.30 to 0.64) | 0.455 (0.30 to 0.64) |

## System

```json
{
  "budget_tokens": 3000,
  "collection": "fb_page_bge-small",
  "mean_sources": 9.15,
  "mean_tokens": 2958,
  "retrieval": "understood filings, three rewrites, fused dense search",
  "split_page_parts": true
}
```
