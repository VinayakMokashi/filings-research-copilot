# routing: cascade-classifier-v1-t0.9 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.891 | 0.833 to 0.942 |
| llm_used | 0.072 | 0.036 to 0.116 |

## By route

| Route | Questions | accuracy | llm_used |
|---|---|---|---|
| brief | 18 | 0.889 (0.72 to 1.00) | 0.056 (0.00 to 0.17) |
| data | 30 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |
| decline | 21 | 0.524 (0.33 to 0.71) | 0.095 (0.00 to 0.24) |
| doc | 30 | 0.900 (0.77 to 1.00) | 0.167 (0.03 to 0.30) |
| hybrid | 21 | 1.000 (1.00 to 1.00) | 0.095 (0.00 to 0.24) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "cost_usd_per_question": 1.47e-05,
  "first": "eval/results/routing/classifier-v1/dev",
  "latency_s": {
    "p50": 0.0094,
    "p95": 0.422
  },
  "router": "cascade (simulated)",
  "second": "eval/results/routing/llm-gpt-oss-120b/dev",
  "threshold": 0.9
}
```
