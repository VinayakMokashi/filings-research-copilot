# sql: sql-agent-v2 (dev)

28 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-22 22:33 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 1.000 | 1.000 to 1.000 |

## By answerable

| Answerable | Questions | accuracy |
|---|---|---|
| answerable | 21 | 1.000 (1.00 to 1.00) |
| unanswerable | 7 | 1.000 (1.00 to 1.00) |

## By difficulty

| Difficulty | Questions | accuracy |
|---|---|---|
| easy | 8 | 1.000 (1.00 to 1.00) |
| hard | 8 | 1.000 (1.00 to 1.00) |
| medium | 12 | 1.000 (1.00 to 1.00) |

## By category

| Category | Questions | accuracy |
|---|---|---|
| aggregate | 2 | 1.000 (1.00 to 1.00) |
| comparison | 1 | 1.000 (1.00 to 1.00) |
| growth | 1 | 1.000 (1.00 to 1.00) |
| lookup | 7 | 1.000 (1.00 to 1.00) |
| provenance | 2 | 1.000 (1.00 to 1.00) |
| ranking | 3 | 1.000 (1.00 to 1.00) |
| ratio | 3 | 1.000 (1.00 to 1.00) |
| trend | 2 | 1.000 (1.00 to 1.00) |
| unanswerable | 7 | 1.000 (1.00 to 1.00) |

## System

```json
{
  "agent": "text2sql-analyst over the facts database, every table offered",
  "errors": 0,
  "helper_model": "groq/qwen/qwen3.8-27b",
  "limit": null,
  "mean_tokens": 3313,
  "model_latency_s": {
    "p50": 1.52,
    "p95": 2.14
  },
  "repaired": 1,
  "sql_model": "groq/openai/gpt-oss-120b",
  "text2sql_analyst": "0.3.0",
  "value_linking": true
}
```
