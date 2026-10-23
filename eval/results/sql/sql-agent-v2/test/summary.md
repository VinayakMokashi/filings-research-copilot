# sql: sql-agent-v2 (test)

14 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 12:27 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 1.000 | 1.000 to 1.000 |

## By answerable

| Answerable | Questions | accuracy |
|---|---|---|
| answerable | 11 | 1.000 (1.00 to 1.00) |
| unanswerable | 3 | 1.000 (1.00 to 1.00) |

## By difficulty

| Difficulty | Questions | accuracy |
|---|---|---|
| easy | 5 | 1.000 (1.00 to 1.00) |
| hard | 4 | 1.000 (1.00 to 1.00) |
| medium | 5 | 1.000 (1.00 to 1.00) |

## By category

| Category | Questions | accuracy |
|---|---|---|
| aggregate | 1 | 1.000 (1.00 to 1.00) |
| comparison | 1 | 1.000 (1.00 to 1.00) |
| lookup | 3 | 1.000 (1.00 to 1.00) |
| provenance | 1 | 1.000 (1.00 to 1.00) |
| ranking | 2 | 1.000 (1.00 to 1.00) |
| ratio | 2 | 1.000 (1.00 to 1.00) |
| trend | 1 | 1.000 (1.00 to 1.00) |
| unanswerable | 3 | 1.000 (1.00 to 1.00) |

## System

```json
{
  "agent": "text2sql-analyst over the facts database, every table offered",
  "errors": 0,
  "helper_model": "groq/qwen/qwen3.8-27b",
  "limit": null,
  "mean_tokens": 3312,
  "model_latency_s": {
    "p50": 1.91,
    "p95": 22.79
  },
  "repaired": 1,
  "sql_model": "groq/openai/gpt-oss-120b",
  "text2sql_analyst": "0.3.0",
  "value_linking": true
}
```
