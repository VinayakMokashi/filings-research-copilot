# correctness: doc-agent-v3-full--qwen3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:43 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.650 | 0.560 to 0.740 |
| incorrect | 0.290 | 0.200 to 0.380 |
| refused | 0.060 | 0.020 to 0.110 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.588 (0.41 to 0.74) | 0.353 (0.21 to 0.53) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.061 (0.00 to 0.15) | 0.061 (0.00 to 0.15) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.455 (0.30 to 0.64) | 0.061 (0.00 to 0.15) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 60895,
  "verdicts": {
    "correct": 65,
    "incorrect": 29,
    "refused": 6
  }
}
```
