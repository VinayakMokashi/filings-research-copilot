# routing: semantic-masked-centroid (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:22 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.739 | 0.667 to 0.812 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.778 (0.56 to 0.94) |
| data | 30 | 0.867 (0.73 to 0.97) |
| decline | 21 | 0.476 (0.29 to 0.67) |
| doc | 30 | 0.800 (0.63 to 0.93) |
| hybrid | 21 | 0.619 (0.43 to 0.81) |
| smalltalk | 18 | 0.833 (0.67 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.739 (0.64 to 0.83) |
| seed | 46 | 0.739 (0.61 to 0.87) |

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
    "p50": 0.0083,
    "p95": 0.0126
  },
  "mask": "entities",
  "mean_tokens": 0,
  "method": "centroid",
  "router": "semantic"
}
```
