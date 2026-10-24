# routing: semantic-centroid (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.543 | 0.457 to 0.630 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.556 (0.33 to 0.78) |
| data | 30 | 0.633 (0.47 to 0.80) |
| decline | 21 | 0.429 (0.24 to 0.62) |
| doc | 30 | 0.600 (0.43 to 0.77) |
| hybrid | 21 | 0.190 (0.05 to 0.38) |
| smalltalk | 18 | 0.833 (0.67 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.522 (0.41 to 0.63) |
| seed | 46 | 0.587 (0.46 to 0.74) |

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
    "p50": 0.0082,
    "p95": 0.0135
  },
  "mask": "none",
  "mean_tokens": 0,
  "method": "centroid",
  "router": "semantic"
}
```
