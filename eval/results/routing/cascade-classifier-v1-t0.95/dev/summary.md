# routing: cascade-classifier-v1-t0.95 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.906 | 0.855 to 0.949 |
| llm_used | 0.116 | 0.065 to 0.174 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.889 (0.72 to 1.00) | 0.111 (0.00 to 0.28) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.033 (0.00 to 0.10) |
| decline | 21 | 0.571 (0.38 to 0.76) | 0.143 (0.00 to 0.29) |
| doc | 30 | 0.933 (0.83 to 1.00) | 0.233 (0.10 to 0.40) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.143 (0.00 to 0.29) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 2.28e-05,
  "first": "eval/results/routing/classifier-v1/dev",
  "latency_s": {
    "p50": 0.0095,
    "p95": 0.783
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.95
}
```
