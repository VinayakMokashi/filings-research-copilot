# correctness: doc-agent-v4-full--gpt-oss-20b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:50 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.630 | 0.540 to 0.720 |
| incorrect | 0.310 | 0.220 to 0.400 |
| refused | 0.060 | 0.020 to 0.110 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.529 (0.35 to 0.71) | 0.412 (0.24 to 0.59) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.061 (0.00 to 0.15) | 0.061 (0.00 to 0.15) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.455 (0.30 to 0.64) | 0.061 (0.00 to 0.15) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "judge_errors": 0,
  "judge_model": "groq/openai/gpt-oss-20b",
  "judge_prompt_version": "2",
  "judge_tokens": 80680,
  "verdicts": {
    "correct": 63,
    "incorrect": 31,
    "refused": 6
  }
}
```
