# routing: semantic-k5-instruction (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.355 | 0.275 to 0.435 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.333 (0.11 to 0.56) |
| data | 30 | 0.533 (0.37 to 0.70) |
| decline | 21 | 0.381 (0.19 to 0.57) |
| doc | 30 | 0.200 (0.07 to 0.33) |
| hybrid | 21 | 0.000 (0.00 to 0.00) |
| smalltalk | 18 | 0.722 (0.50 to 0.94) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.391 (0.29 to 0.49) |
| seed | 46 | 0.283 (0.15 to 0.41) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "embedder": "BAAI/bge-small-en-v1.5",
  "errors": 0,
  "examples": "routing set dev, each question's own seed group left out",
  "instruction": true,
  "k": 5,
  "latency_s": {
    "p50": 0.0096,
    "p95": 0.0141
  },
  "mask": "none",
  "mean_tokens": 0,
  "method": "vote",
  "router": "semantic"
}
```
