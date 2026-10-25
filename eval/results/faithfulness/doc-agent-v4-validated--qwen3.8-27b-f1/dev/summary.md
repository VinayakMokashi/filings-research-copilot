# faithfulness: doc-agent-v4-validated--qwen3.8-27b-f1 (dev)

92 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-25 10:06 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.848 | 0.772 to 0.924 |
| supported_share | 0.906 | 0.849 to 0.955 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.781 (0.62 to 0.91) | 0.891 (0.79 to 0.97) |
| metrics-generated | 30 | 0.967 (0.90 to 1.00) | 0.989 (0.97 to 1.00) |
| novel-generated | 30 | 0.800 (0.67 to 0.93) | 0.839 (0.71 to 0.95) |

## System

```json
{
  "answers_run": "doc-agent-v4-validated",
  "citation_precision": 1.0,
  "citations": 248,
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_tokens": 128747,
  "prompt_version": "1"
}
```
