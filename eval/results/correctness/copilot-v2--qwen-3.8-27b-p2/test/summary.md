# correctness: copilot-v2--qwen-3.8-27b-p2 (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:45 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.680 | 0.560 to 0.800 |
| incorrect | 0.260 | 0.140 to 0.380 |
| refused | 0.060 | 0.000 to 0.140 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 16 | 0.625 (0.38 to 0.88) | 0.375 (0.12 to 0.62) | 0.000 (0.00 to 0.00) |
| metrics-generated | 17 | 0.941 (0.82 to 1.00) | 0.059 (0.00 to 0.18) | 0.000 (0.00 to 0.00) |
| novel-generated | 17 | 0.471 (0.24 to 0.71) | 0.353 (0.12 to 0.59) | 0.176 (0.00 to 0.35) |

## System

```json
{
  "answers_run": "copilot-v2",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 32732,
  "verdicts": {
    "correct": 34,
    "incorrect": 13,
    "refused": 3
  }
}
```
