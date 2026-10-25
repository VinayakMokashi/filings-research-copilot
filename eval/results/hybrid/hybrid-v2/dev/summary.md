# hybrid: hybrid-v2 (dev)

13 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-25 02:42 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 1.000 | 1.000 to 1.000 |
| figures_given | 1.000 | 1.000 to 1.000 |
| all_figures | 1.000 | 1.000 to 1.000 |
| database_cited | 0.231 | 0.000 to 0.462 |
| pages_cited | 1.000 | 1.000 to 1.000 |
| faithful | 0.538 | 0.231 to 0.769 |
| supported | 0.833 | 0.724 to 0.936 |

## System

```json
{
  "agent": "hybrid-v2",
  "answer_model": "groq/openai/gpt-oss-120b",
  "cost_usd_per_question": 0.003355,
  "faithfulness_judge": "groq/qwen/qwen3.8-27b, prompt 1",
  "hybrid_prompt": "2",
  "mean_tokens": 7638,
  "model_latency_s": {
    "max": 241.83,
    "p50": 5.03
  },
  "paths": {
    "doc": 10,
    "split": 3
  },
  "questions": "eval/hybrid/questions.jsonl, 13 on dev companies",
  "retried": 2
}
```
