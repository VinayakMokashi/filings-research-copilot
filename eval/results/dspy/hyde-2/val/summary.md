# dspy: hyde-2 (val)

104 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 22:39 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| rr@10 | 0.497 | 0.427 to 0.567 |
| words | 48.760 | 43.827 to 53.942 |

## System

```json
{
  "instruction": "You write short excerpts in the style of SEC filings. Write the passage, three to five sentences, that the company's filing would contain to answer this question, in the filing's own wording: a few lines of a financial statement, or a paragraph of management's discussion. Use plausible figures if you don't know the real ones. Return only the passage.",
  "metric": "reciprocal rank to 10, within the filing",
  "model": "cerebras/qwen-3.8-27b",
  "prompt_version": "2"
}
```
