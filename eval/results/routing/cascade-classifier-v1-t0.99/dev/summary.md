# routing: cascade-classifier-v1-t0.99 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.978 | 0.949 to 1.000 |
| llm_used | 0.326 | 0.254 to 0.406 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.944 (0.83 to 1.00) | 0.444 (0.22 to 0.67) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.033 (0.00 to 0.10) |
| decline | 21 | 0.905 (0.76 to 1.00) | 0.619 (0.43 to 0.81) |
| doc | 30 | 1.000 (1.00 to 1.00) | 0.500 (0.33 to 0.67) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.286 (0.10 to 0.48) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.111 (0.00 to 0.28) |

## System

```json
{
  "cost_usd_per_question": 6.3e-05,
  "first": "eval/results/routing/classifier-v1/dev",
  "latency_s": {
    "p50": 0.011,
    "p95": 0.8339
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.99
}
```
