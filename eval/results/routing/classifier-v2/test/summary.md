# routing: classifier-v2 (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 05:15 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.950 | 0.883 to 1.000 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 6 | 0.667 (0.33 to 1.00) |
| data | 15 | 1.000 (1.00 to 1.00) |
| decline | 9 | 1.000 (1.00 to 1.00) |
| doc | 15 | 0.933 (0.80 to 1.00) |
| hybrid | 9 | 1.000 (1.00 to 1.00) |
| smalltalk | 6 | 1.000 (1.00 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 40 | 0.925 (0.82 to 1.00) |
| seed | 20 | 1.000 (1.00 to 1.00) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "errors": 0,
  "latency_s": {
    "p50": 0.0079,
    "p95": 0.0125
  },
  "mean_tokens": 0,
  "model": "router-v2",
  "router": "classifier",
  "sha256": "d116fcc08b81289ba60c39b0b54d162e9975890ad7d463ab3c88d80ec18c442c"
}
```
