# hybrid: doc-agent-v4 (dev)

13 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 10:15 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.769 | 0.538 to 1.000 |
| figures_given | 0.769 | 0.538 to 1.000 |
| all_figures | 0.769 | 0.538 to 1.000 |
| database_cited | 0.000 | 0.000 to 0.000 |
| pages_cited | 0.769 | 0.538 to 1.000 |
| faithful | 0.462 | 0.231 to 0.692 |
| supported | 0.667 | 0.442 to 0.865 |

## System

```json
{
  "agent": "doc",
  "answer_model": "groq/openai/gpt-oss-120b",
  "cost_usd_per_question": 0.003017,
  "faithfulness_judge": "groq/qwen/qwen3.8-27b, prompt 1",
  "mean_tokens": 7318,
  "model_latency_s": {
    "max": 73.16,
    "p50": 5.03
  },
  "questions": "eval/hybrid/questions.jsonl, 13 on dev companies"
}
```
