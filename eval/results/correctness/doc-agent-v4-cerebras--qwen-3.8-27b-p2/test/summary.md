# correctness: doc-agent-v4-cerebras--qwen-3.8-27b-p2 (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:46 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.660 | 0.520 to 0.780 |
| incorrect | 0.300 | 0.180 to 0.420 |
| refused | 0.040 | 0.000 to 0.100 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 16 | 0.625 (0.38 to 0.88) | 0.375 (0.12 to 0.62) | 0.000 (0.00 to 0.00) |
| metrics-generated | 17 | 0.765 (0.53 to 0.94) | 0.118 (0.00 to 0.29) | 0.118 (0.00 to 0.29) |
| novel-generated | 17 | 0.588 (0.35 to 0.82) | 0.412 (0.18 to 0.65) | 0.000 (0.00 to 0.00) |

## System

```json
{
  "answers_run": "doc-agent-v4-cerebras",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 33895,
  "verdicts": {
    "correct": 33,
    "incorrect": 15,
    "refused": 2
  }
}
```
