# routing: semantic-masked-k5 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.522 | 0.435 to 0.609 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.889 (0.72 to 1.00) |
| data | 30 | 0.700 (0.53 to 0.87) |
| decline | 21 | 0.286 (0.10 to 0.48) |
| doc | 30 | 0.467 (0.30 to 0.63) |
| hybrid | 21 | 0.048 (0.00 to 0.14) |
| smalltalk | 18 | 0.778 (0.56 to 0.94) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.522 (0.42 to 0.62) |
| seed | 46 | 0.522 (0.39 to 0.65) |

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
    "p50": 0.008,
    "p95": 0.0124
  },
  "mask": "entities",
  "mean_tokens": 0,
  "method": "vote",
  "router": "semantic"
}
```
