# context: page-rw-all-understood-b1500 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| context_hit | 0.520 | 0.420 to 0.620 |
| context_recall | 0.500 | 0.400 to 0.595 |

## By question type

| Question type | Questions | context_hit | context_recall |
|---|---|---|---|
| domain-relevant | 34 | 0.382 (0.21 to 0.56) | 0.353 (0.21 to 0.51) |
| metrics-generated | 33 | 0.818 (0.67 to 0.94) | 0.788 (0.65 to 0.91) |
| novel-generated | 33 | 0.364 (0.21 to 0.52) | 0.364 (0.21 to 0.52) |

## System

```json
{
  "budget_tokens": 1500,
  "collection": "fb_page_bge-small",
  "mean_sources": 4.23,
  "mean_tokens": 1462,
  "retrieval": "understood filings, three rewrites, fused dense search",
  "split_page_parts": false
}
```
