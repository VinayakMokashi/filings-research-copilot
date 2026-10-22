# sql: sql-agent-v1 (dev)

28 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-22 22:08 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.607 | 0.429 to 0.786 |

## By answerable

| Answerable | Questions | accuracy |
|---|---|---|
| answerable | 21 | 0.571 (0.38 to 0.76) |
| unanswerable | 7 | 0.714 (0.29 to 1.00) |

## By difficulty

| Difficulty | Questions | accuracy |
|---|---|---|
| easy | 8 | 0.500 (0.12 to 0.88) |
| hard | 8 | 0.500 (0.12 to 0.88) |
| medium | 12 | 0.750 (0.50 to 1.00) |

## By category

| Category | Questions | accuracy |
|---|---|---|
| aggregate | 2 | 1.000 (1.00 to 1.00) |
| comparison | 1 | 1.000 (1.00 to 1.00) |
| growth | 1 | 1.000 (1.00 to 1.00) |
| lookup | 7 | 0.571 (0.14 to 0.86) |
| provenance | 2 | 0.500 (0.00 to 1.00) |
| ranking | 3 | 0.333 (0.00 to 1.00) |
| ratio | 3 | 0.333 (0.00 to 1.00) |
| trend | 2 | 0.500 (0.00 to 1.00) |
| unanswerable | 7 | 0.714 (0.29 to 1.00) |

## System

```json
{
  "agent": "text2sql-analyst over the facts database, every table offered",
  "errors": 0,
  "helper_model": "groq/qwen/qwen3.8-27b",
  "limit": null,
  "mean_tokens": 2345,
  "model_latency_s": {
    "p50": 1.56,
    "p95": 2.16
  },
  "repaired": 0,
  "sql_model": "groq/openai/gpt-oss-120b",
  "text2sql_analyst": "0.2.0"
}
```
