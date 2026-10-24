# routing: llm-gpt-oss-20b (dev)

138 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 19:53 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.964 | 0.928 to 0.993 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 18 | 0.944 (0.83 to 1.00) |
| data | 30 | 1.000 (1.00 to 1.00) |
| decline | 21 | 0.905 (0.76 to 1.00) |
| doc | 30 | 1.000 (1.00 to 1.00) |
| hybrid | 21 | 1.000 (1.00 to 1.00) |
| smalltalk | 18 | 0.889 (0.72 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 92 | 0.967 (0.92 to 1.00) |
| seed | 46 | 0.957 (0.89 to 1.00) |

## System

```json
{
  "cost_usd_per_question": 0.0001019,
  "errors": 0,
  "latency_s": {
    "p50": 0.6787,
    "p95": 1.1593
  },
  "mean_tokens": 997,
  "model": "groq/openai/gpt-oss-20b",
  "prompt_version": "r1",
  "router": "llm"
}
```
