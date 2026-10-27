# correctness: arm-strong-low--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 22:12 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.630 | 0.530 to 0.720 |
| incorrect | 0.230 | 0.150 to 0.310 |
| refused | 0.140 | 0.080 to 0.210 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.500 (0.32 to 0.68) | 0.353 (0.21 to 0.53) | 0.147 (0.03 to 0.26) |
| metrics-generated | 33 | 0.909 (0.79 to 1.00) | 0.061 (0.00 to 0.15) | 0.030 (0.00 to 0.09) |
| novel-generated | 33 | 0.485 (0.30 to 0.67) | 0.273 (0.12 to 0.42) | 0.242 (0.09 to 0.39) |

## System

```json
{
  "answers_run": "arm-strong-low",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 61649,
  "verdicts": {
    "correct": 63,
    "incorrect": 23,
    "refused": 14
  }
}
```
