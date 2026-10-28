# briefs: crew-v1 (dev)

12 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 21:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| rubric | 0.863 | 0.754 to 0.963 |
| faithful_share | 0.916 | 0.859 to 0.962 |
| faithful | 0.333 | 0.083 to 0.583 |
| sources | 7.083 | 5.583 to 8.500 |
| words | 410.833 | 319.081 to 503.585 |
| cost_usd | 0.015 | 0.014 to 0.017 |
| seconds | 91.400 | 71.925 to 105.800 |

## System

```json
{
  "briefs": 12,
  "critic": "groq/openai/gpt-oss-20b",
  "judge": "cerebras/qwen-3.8-27b",
  "planner_and_editor": "cerebras/gpt-oss-120b",
  "rubric_items": 57,
  "rubric_prompt_version": "1",
  "system": "crew",
  "writers": {
    "doc": "cerebras/gpt-oss-120b",
    "hybrid": "cerebras/gpt-oss-120b"
  }
}
```
