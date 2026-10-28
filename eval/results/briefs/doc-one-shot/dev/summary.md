# briefs: doc-one-shot (dev)

12 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-28 01:11 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| rubric | 0.658 | 0.442 to 0.854 |
| faithful_share | 0.764 | 0.542 to 0.958 |
| faithful | 0.667 | 0.417 to 0.917 |
| sources | 3.000 | 2.083 to 3.750 |
| words | 97.000 | 67.750 to 123.252 |
| cost_usd | 0.004 | 0.004 to 0.005 |
| seconds | 0.400 | 0.325 to 0.483 |

## System

```json
{
  "briefs": 12,
  "critic": "groq/openai/gpt-oss-20b",
  "judge": "cerebras/qwen-3.8-27b",
  "planner_and_editor": "cerebras/gpt-oss-120b",
  "rubric_items": 57,
  "rubric_prompt_version": "1",
  "system": "doc",
  "writers": {
    "doc": "cerebras/gpt-oss-120b",
    "hybrid": "cerebras/gpt-oss-120b"
  }
}
```
