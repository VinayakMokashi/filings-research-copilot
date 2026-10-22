# faithfulness: doc-agent-v4-full--qwen3.8-27b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:52 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.628 | 0.532 to 0.723 |
| supported_share | 0.771 | 0.698 to 0.840 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.406 (0.25 to 0.56) | 0.716 (0.61 to 0.82) |
| metrics-generated | 31 | 0.871 (0.74 to 0.97) | 0.909 (0.81 to 0.99) |
| novel-generated | 31 | 0.613 (0.45 to 0.77) | 0.691 (0.54 to 0.83) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "citation_precision": 0.9341,
  "citations": 258,
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_tokens": 128657,
  "prompt_version": "1"
}
```
