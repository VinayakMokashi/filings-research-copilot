# routing: cascade-classifier-v2-t0.98 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.964 | 0.928 to 0.993 |
| llm_used | 0.225 | 0.159 to 0.297 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.944 (0.83 to 1.00) | 0.444 (0.22 to 0.67) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.033 (0.00 to 0.10) |
| decline | 21 | 0.810 (0.62 to 0.95) | 0.190 (0.05 to 0.38) |
| doc | 30 | 1.000 (1.00 to 1.00) | 0.367 (0.20 to 0.53) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.333 (0.14 to 0.52) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 4.43e-05,
  "first": "eval/results/routing/classifier-v2/dev",
  "latency_s": {
    "p50": 0.0083,
    "p95": 0.8126
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.98
}
```
