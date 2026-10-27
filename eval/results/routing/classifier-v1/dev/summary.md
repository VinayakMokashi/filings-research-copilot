# routing: classifier-v1 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:26 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.833 | 0.768 to 0.891 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.833 (0.67 to 1.00) |
| data | 30 | 1.000 (1.00 to 1.00) |
| decline | 21 | 0.429 (0.24 to 0.67) |
| doc | 30 | 0.767 (0.60 to 0.90) |
| hybrid | 21 | 0.952 (0.86 to 1.00) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.826 (0.75 to 0.90) |
| seed | 46 | 0.848 (0.74 to 0.93) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "errors": 0,
  "latency_s": {
    "p50": 0.0094,
    "p95": 0.0157
  },
  "mean_tokens": 0,
  "model": "router-v1",
  "router": "classifier",
  "sha256": "f6e94ac72a74347a055f24e888c80491e2072bce9589842c22be383bc3489459"
}
```
