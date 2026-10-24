# routing: semantic-k10 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.442 | 0.362 to 0.522 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.444 (0.22 to 0.67) |
| data | 30 | 0.733 (0.57 to 0.87) |
| decline | 21 | 0.286 (0.10 to 0.48) |
| doc | 30 | 0.233 (0.10 to 0.40) |
| hybrid | 21 | 0.095 (0.00 to 0.24) |
| smalltalk | 18 | 0.889 (0.72 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.435 (0.34 to 0.54) |
| seed | 46 | 0.457 (0.33 to 0.59) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "embedder": "BAAI/bge-small-en-v1.5",
  "errors": 0,
  "examples": "routing set dev, each question's own seed group left out",
  "instruction": false,
  "k": 10,
  "latency_s": {
    "p50": 0.0075,
    "p95": 0.012
  },
  "mask": "none",
  "mean_tokens": 0,
  "method": "vote",
  "router": "semantic"
}
```
