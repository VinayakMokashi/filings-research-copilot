# routing: semantic-k5 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.391 | 0.312 to 0.471 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.389 (0.17 to 0.61) |
| data | 30 | 0.567 (0.40 to 0.73) |
| decline | 21 | 0.429 (0.24 to 0.62) |
| doc | 30 | 0.167 (0.03 to 0.30) |
| hybrid | 21 | 0.048 (0.00 to 0.14) |
| smalltalk | 18 | 0.833 (0.67 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.413 (0.32 to 0.51) |
| seed | 46 | 0.348 (0.22 to 0.48) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "embedder": "BAAI/bge-small-en-v1.5",
  "errors": 0,
  "examples": "routing set dev, each question's own seed group left out",
  "instruction": false,
  "k": 5,
  "latency_s": {
    "p50": 0.0076,
    "p95": 0.0118
  },
  "mask": "none",
  "mean_tokens": 0,
  "method": "vote",
  "router": "semantic"
}
```
