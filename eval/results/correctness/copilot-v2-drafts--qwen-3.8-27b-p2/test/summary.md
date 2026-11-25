# correctness: copilot-v2-drafts--qwen-3.8-27b-p2 (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:46 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.700 | 0.580 to 0.820 |
| incorrect | 0.300 | 0.180 to 0.420 |
| refused | 0.000 | 0.000 to 0.000 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 16 | 0.625 (0.38 to 0.88) | 0.375 (0.12 to 0.62) | 0.000 (0.00 to 0.00) |
| metrics-generated | 17 | 0.941 (0.82 to 1.00) | 0.059 (0.00 to 0.18) | 0.000 (0.00 to 0.00) |
| novel-generated | 17 | 0.529 (0.29 to 0.76) | 0.471 (0.24 to 0.71) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "answers_run": "copilot-v2-drafts",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 34840,
  "verdicts": {
    "correct": 35,
    "incorrect": 15
  }
}
```
