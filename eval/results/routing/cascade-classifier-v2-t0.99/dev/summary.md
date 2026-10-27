# routing: cascade-classifier-v2-t0.99 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.978 | 0.949 to 1.000 |
| llm_used | 0.355 | 0.282 to 0.435 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.944 (0.83 to 1.00) | 0.944 (0.83 to 1.00) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.067 (0.00 to 0.17) |
| decline | 21 | 0.905 (0.76 to 1.00) | 0.381 (0.19 to 0.57) |
| doc | 30 | 1.000 (1.00 to 1.00) | 0.500 (0.33 to 0.67) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.333 (0.14 to 0.52) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 6.88e-05,
  "first": "eval/results/routing/classifier-v2/dev",
  "latency_s": {
    "p50": 0.0086,
    "p95": 0.8171
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.99
}
```
