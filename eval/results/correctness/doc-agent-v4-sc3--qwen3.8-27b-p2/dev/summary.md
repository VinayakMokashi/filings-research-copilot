# correctness: doc-agent-v4-sc3--qwen3.8-27b-p2 (dev)

33 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 21:19 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.879 | 0.758 to 0.970 |
| incorrect | 0.061 | 0.000 to 0.152 |
| refused | 0.061 | 0.000 to 0.152 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.061 (0.00 to 0.15) | 0.061 (0.00 to 0.15) |

## System

```json
{
  "answers_run": "doc-agent-v4-sc3",
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 20043,
  "verdicts": {
    "correct": 29,
    "incorrect": 2,
    "refused": 2
  }
}
```
