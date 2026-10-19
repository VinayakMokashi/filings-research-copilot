# context: page-rw-all-understood-b1500-siblings (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| context_hit | 0.510 | 0.410 to 0.610 |
| context_recall | 0.480 | 0.385 to 0.575 |

## By question type

| Question type | Questions | context_hit | context_recall |
|---|---|---|---|
| domain-relevant | 34 | 0.412 (0.24 to 0.59) | 0.368 (0.22 to 0.53) |
| metrics-generated | 33 | 0.788 (0.64 to 0.91) | 0.742 (0.59 to 0.88) |
| novel-generated | 33 | 0.333 (0.18 to 0.48) | 0.333 (0.18 to 0.48) |

## System

```json
{
  "budget_tokens": 1500,
  "collection": "fb_page_bge-small",
  "mean_sources": 4.87,
  "mean_tokens": 1462,
  "retrieval": "understood filings, three rewrites, fused dense search",
  "split_page_parts": true
}
```
