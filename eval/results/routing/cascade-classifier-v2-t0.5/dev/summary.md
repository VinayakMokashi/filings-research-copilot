# routing: cascade-classifier-v2-t0.5 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.920 | 0.877 to 0.964 |
| llm_used | 0.007 | 0.000 to 0.022 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.778 (0.56 to 0.94) | 0.056 (0.00 to 0.17) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |
| decline | 21 | 0.762 (0.57 to 0.90) | 0.000 (0.00 to 0.00) |
| doc | 30 | 0.933 (0.83 to 1.00) | 0.000 (0.00 to 0.00) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 1.6e-06,
  "first": "eval/results/routing/classifier-v2/dev",
  "latency_s": {
    "p50": 0.008,
    "p95": 0.012
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.5
}
```
