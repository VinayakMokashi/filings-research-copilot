# correctness: doc-agent-v3-full--gpt-oss-20b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-21 15:44 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.640 | 0.550 to 0.730 |
| incorrect | 0.300 | 0.210 to 0.390 |
| refused | 0.060 | 0.020 to 0.110 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.559 (0.38 to 0.74) | 0.382 (0.24 to 0.56) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.061 (0.00 to 0.15) | 0.061 (0.00 to 0.15) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.455 (0.30 to 0.64) | 0.061 (0.00 to 0.15) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "judge_errors": 0,
  "judge_model": "groq/openai/gpt-oss-20b",
  "judge_prompt_version": "2",
  "judge_tokens": 81079,
  "verdicts": {
    "correct": 64,
    "incorrect": 30,
    "refused": 6
  }
}
```
