# answers: data-agent-v1-postgres (dev)

33 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-28 03:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 1.000 | 1.000 to 1.000 |
| declined | 0.000 | 0.000 to 0.000 |
| failed | 0.000 | 0.000 to 0.000 |
| repaired | 0.030 | 0.000 to 0.091 |

## By question type

| Question type | Questions | answered | declined | failed | repaired |
|---|---|---|---|---|---|
| metrics-generated | 33 | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 0.030 (0.00 to 0.09) |

## System

```json
{
  "agent": "the data agent: text2sql-analyst over the facts database, value linking",
  "analysis_model": "groq/openai/gpt-oss-120b",
  "cost_usd": {
    "per_question": 0.002544,
    "priced_questions": 33,
    "total": 0.084
  },
  "limit": null,
  "mean_completion_tokens": 863,
  "mean_prompt_tokens": 4005,
  "model_latency_s": {
    "p50": 2.78,
    "p95": 4.09
  },
  "question_types": [
    "metrics-generated"
  ],
  "selection_model": "groq/qwen/qwen3.8-27b",
  "sql_model": "groq/openai/gpt-oss-120b",
  "text2sql_analyst": "0.3.0"
}
```
