# correctness: data-agent-v1--gpt-oss-20b-p2 (dev)

33 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-22 23:34 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.970 | 0.909 to 1.000 |
| incorrect | 0.030 | 0.000 to 0.091 |
| refused | 0.000 | 0.000 to 0.000 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| metrics-generated | 33 | 0.970 (0.91 to 1.00) | 0.030 (0.00 to 0.09) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "answers_run": "data-agent-v1",
  "judge_errors": 0,
  "judge_model": "groq/openai/gpt-oss-20b",
  "judge_prompt_version": "2",
  "judge_tokens": 23381,
  "verdicts": {
    "correct": 32,
    "incorrect": 1
  }
}
```
