# routing: cascade-classifier-v1-t0.995 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 1.000 | 1.000 to 1.000 |
| llm_used | 0.522 | 0.442 to 0.609 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 1.000 (1.00 to 1.00) | 0.778 (0.56 to 0.94) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.033 (0.00 to 0.10) |
| decline | 21 | 1.000 (1.00 to 1.00) | 0.810 (0.62 to 0.95) |
| doc | 30 | 1.000 (1.00 to 1.00) | 0.700 (0.53 to 0.87) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.476 (0.29 to 0.67) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.500 (0.28 to 0.72) |

## System

```json
{
  "cost_usd_per_question": 0.0001,
  "first": "eval/results/routing/classifier-v1/dev",
  "latency_s": {
    "p50": 0.3398,
    "p95": 1.1093
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.995
}
```
