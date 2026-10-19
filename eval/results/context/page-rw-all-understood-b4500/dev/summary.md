# context: page-rw-all-understood-b4500 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-19 17:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| context_hit | 0.730 | 0.640 to 0.810 |
| context_recall | 0.712 | 0.622 to 0.795 |

## By question type

| Question type | Questions | context_hit | context_recall |
|---|---|---|---|
| domain-relevant | 34 | 0.647 (0.47 to 0.79) | 0.608 (0.45 to 0.76) |
| metrics-generated | 33 | 0.939 (0.85 to 1.00) | 0.924 (0.83 to 1.00) |
| novel-generated | 33 | 0.606 (0.42 to 0.76) | 0.606 (0.42 to 0.76) |

## System

```json
{
  "budget_tokens": 4500,
  "collection": "fb_page_bge-small",
  "mean_sources": 11.75,
  "mean_tokens": 4456,
  "retrieval": "understood filings, three rewrites, fused dense search",
  "split_page_parts": false
}
```
