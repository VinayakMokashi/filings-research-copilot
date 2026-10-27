# routing: llm-r2-gpt-oss-120b-cerebras (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 03:37 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 1.000 | 1.000 to 1.000 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 1.000 (1.00 to 1.00) |
| data | 30 | 1.000 (1.00 to 1.00) |
| decline | 21 | 1.000 (1.00 to 1.00) |
| doc | 30 | 1.000 (1.00 to 1.00) |
| hybrid | 21 | 1.000 (1.00 to 1.00) |
| smalltalk | 18 | 1.000 (1.00 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 1.000 (1.00 to 1.00) |
| seed | 46 | 1.000 (1.00 to 1.00) |

## System

```json
{
  "cost_usd_per_question": 0.0004236,
  "errors": 0,
  "latency_s": {
    "p50": 0.4733,
    "p95": 0.7356
  },
  "mean_tokens": 1090,
  "model": "cerebras/gpt-oss-120b",
  "prompt_version": "r2",
  "router": "llm"
}
```
