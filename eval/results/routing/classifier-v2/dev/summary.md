# routing: classifier-v2 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.913 | 0.862 to 0.957 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.722 (0.50 to 0.89) |
| data | 30 | 1.000 (1.00 to 1.00) |
| decline | 21 | 0.762 (0.57 to 0.90) |
| doc | 30 | 0.933 (0.83 to 1.00) |
| hybrid | 21 | 1.000 (1.00 to 1.00) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.913 (0.85 to 0.97) |
| seed | 46 | 0.913 (0.83 to 0.98) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "errors": 0,
  "latency_s": {
    "p50": 0.008,
    "p95": 0.012
  },
  "mean_tokens": 0,
  "model": "router-v2",
  "router": "classifier",
  "sha256": "d116fcc08b81289ba60c39b0b54d162e9975890ad7d463ab3c88d80ec18c442c"
}
```
