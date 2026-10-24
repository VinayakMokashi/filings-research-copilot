# routing: semantic-masked-centroid (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-24 15:22 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.800 | 0.700 to 0.900 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 6 | 1.000 (1.00 to 1.00) |
| data | 15 | 0.933 (0.80 to 1.00) |
| decline | 9 | 0.222 (0.00 to 0.56) |
| doc | 15 | 1.000 (1.00 to 1.00) |
| hybrid | 9 | 0.667 (0.33 to 1.00) |
| smalltalk | 6 | 0.833 (0.50 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 40 | 0.800 (0.68 to 0.93) |
| seed | 20 | 0.800 (0.60 to 0.95) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "embedder": "BAAI/bge-small-en-v1.5",
  "errors": 0,
  "examples": "routing set dev, each question's own seed group left out",
  "instruction": false,
  "k": null,
  "latency_s": {
    "p50": 0.0081,
    "p95": 0.0127
  },
  "mask": "entities",
  "mean_tokens": 0,
  "method": "centroid",
  "router": "semantic"
}
```
