# routing: cascade-classifier-v2-t0.8 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.957 | 0.920 to 0.986 |
| llm_used | 0.087 | 0.043 to 0.138 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.889 (0.72 to 1.00) | 0.278 (0.11 to 0.50) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |
| decline | 21 | 0.810 (0.62 to 0.95) | 0.048 (0.00 to 0.14) |
| doc | 30 | 1.000 (1.00 to 1.00) | 0.167 (0.03 to 0.30) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.048 (0.00 to 0.14) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 1.71e-05,
  "first": "eval/results/routing/classifier-v2/dev",
  "latency_s": {
    "p50": 0.0082,
    "p95": 0.6141
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.8
}
```
