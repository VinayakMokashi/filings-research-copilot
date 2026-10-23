# hybrid: hybrid-v1 (dev)

13 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-23 14:54 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.769 | 0.538 to 1.000 |
| figures_given | 0.769 | 0.538 to 1.000 |
| all_figures | 0.769 | 0.538 to 1.000 |
| database_cited | 0.692 | 0.462 to 0.923 |
| pages_cited | 0.769 | 0.538 to 1.000 |
| faithful | 0.615 | 0.385 to 0.846 |
| supported | 0.715 | 0.469 to 0.923 |

## System

```json
{
  "agent": "hybrid",
  "answer_model": "groq/openai/gpt-oss-120b",
  "cost_usd_per_question": 0.004777,
  "faithfulness_judge": "groq/qwen/qwen3.8-27b, prompt 1",
  "mean_tokens": 9701,
  "model_latency_s": {
    "max": 37.36,
    "p50": 7.03
  },
  "questions": "eval/hybrid/questions.jsonl, 13 on dev companies"
}
```
