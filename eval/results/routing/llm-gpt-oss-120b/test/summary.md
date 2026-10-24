# routing: llm-gpt-oss-120b (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-24 15:18 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 1.000 | 1.000 to 1.000 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 6 | 1.000 (1.00 to 1.00) |
| data | 15 | 1.000 (1.00 to 1.00) |
| decline | 9 | 1.000 (1.00 to 1.00) |
| doc | 15 | 1.000 (1.00 to 1.00) |
| hybrid | 9 | 1.000 (1.00 to 1.00) |
| smalltalk | 6 | 1.000 (1.00 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 40 | 1.000 (1.00 to 1.00) |
| seed | 20 | 1.000 (1.00 to 1.00) |

## System

```json
{
  "cost_usd_per_question": 0.0001822,
  "errors": 0,
  "latency_s": {
    "p50": 0.8337,
    "p95": 47.7384
  },
  "mean_tokens": 961,
  "model": "groq/openai/gpt-oss-120b",
  "prompt_version": "r1",
  "router": "llm"
}
```
