# correctness: doc-agent-v4-validated--qwen3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-25 10:09 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.610 | 0.510 to 0.710 |
| incorrect | 0.310 | 0.220 to 0.400 |
| refused | 0.080 | 0.030 to 0.140 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.441 (0.29 to 0.62) | 0.500 (0.32 to 0.68) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.030 (0.00 to 0.09) | 0.091 (0.00 to 0.21) |
| novel-generated | 33 | 0.515 (0.33 to 0.70) | 0.394 (0.24 to 0.58) | 0.091 (0.00 to 0.21) |

## System

```json
{
  "answers_run": "doc-agent-v4-validated",
  "judge_errors": 0,
  "judge_model": "groq/qwen/qwen3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 59316,
  "verdicts": {
    "correct": 61,
    "incorrect": 31,
    "refused": 8
  }
}
```
