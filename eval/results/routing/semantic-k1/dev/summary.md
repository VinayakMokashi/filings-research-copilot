# routing: semantic-k1 (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:21 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.319 | 0.246 to 0.399 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.333 (0.11 to 0.56) |
| data | 30 | 0.467 (0.30 to 0.63) |
| decline | 21 | 0.190 (0.05 to 0.38) |
| doc | 30 | 0.167 (0.03 to 0.30) |
| hybrid | 21 | 0.000 (0.00 to 0.00) |
| smalltalk | 18 | 0.833 (0.67 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.326 (0.23 to 0.42) |
| seed | 46 | 0.304 (0.17 to 0.43) |

## System

```json
{
  "cost_usd_per_question": 0.0,
  "embedder": "BAAI/bge-small-en-v1.5",
  "errors": 0,
  "examples": "routing set dev, each question's own seed group left out",
  "instruction": false,
  "k": 1,
  "latency_s": {
    "p50": 0.0078,
    "p95": 0.0117
  },
  "mask": "none",
  "mean_tokens": 0,
  "method": "vote",
  "router": "semantic"
}
```
