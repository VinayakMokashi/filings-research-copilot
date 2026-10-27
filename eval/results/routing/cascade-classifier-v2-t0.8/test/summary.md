# routing: cascade-classifier-v2-t0.8 (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:16 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.967 | 0.917 to 1.000 |
| llm_used | 0.050 | 0.000 to 0.117 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 6 | 0.667 (0.33 to 1.00) | 0.000 (0.00 to 0.00) |
| data | 15 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |
| decline | 9 | 1.000 (1.00 to 1.00) | 0.111 (0.00 to 0.33) |
| doc | 15 | 1.000 (1.00 to 1.00) | 0.067 (0.00 to 0.20) |
| hybrid | 9 | 1.000 (1.00 to 1.00) | 0.111 (0.00 to 0.33) |
| smalltalk | 6 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 9.1e-06,
  "first": "eval/results/routing/classifier-v2/test",
  "latency_s": {
    "p50": 0.0079,
    "p95": 0.0264
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/test",
  "threshold": 0.8
}
```
