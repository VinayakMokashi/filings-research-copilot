# faithfulness: doc-agent-v3-full--qwen3.8-27b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:45 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.617 | 0.521 to 0.713 |
| supported_share | 0.755 | 0.681 to 0.826 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.406 (0.25 to 0.56) | 0.701 (0.59 to 0.81) |
| metrics-generated | 31 | 0.871 (0.74 to 0.97) | 0.909 (0.81 to 0.99) |
| novel-generated | 31 | 0.581 (0.42 to 0.74) | 0.659 (0.50 to 0.81) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "citation_precision": 0.9186,
  "citations": 258,
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_tokens": 128491,
  "prompt_version": "1"
}
```
