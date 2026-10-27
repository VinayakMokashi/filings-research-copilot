# routing: cascade-classifier-v1-t0.98 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.935 | 0.891 to 0.971 |
| llm_used | 0.196 | 0.130 to 0.268 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.944 (0.83 to 1.00) | 0.333 (0.11 to 0.56) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.033 (0.00 to 0.10) |
| decline | 21 | 0.667 (0.48 to 0.86) | 0.333 (0.14 to 0.52) |
| doc | 30 | 0.967 (0.90 to 1.00) | 0.300 (0.13 to 0.47) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.190 (0.05 to 0.38) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 3.77e-05,
  "first": "eval/results/routing/classifier-v1/dev",
  "latency_s": {
    "p50": 0.0098,
    "p95": 0.7879
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.98
}
```
