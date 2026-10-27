# correctness: copilot-v2--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 04:27 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.650 | 0.560 to 0.740 |
| incorrect | 0.260 | 0.180 to 0.350 |
| refused | 0.090 | 0.040 to 0.150 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.471 (0.29 to 0.65) | 0.441 (0.29 to 0.62) | 0.088 (0.00 to 0.21) |
| metrics-generated | 33 | 0.970 (0.91 to 1.00) | 0.030 (0.00 to 0.09) | 0.000 (0.00 to 0.00) |
| novel-generated | 33 | 0.515 (0.33 to 0.67) | 0.303 (0.15 to 0.45) | 0.182 (0.06 to 0.30) |

## System

```json
{
  "answers_run": "copilot-v2",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 64980,
  "verdicts": {
    "correct": 65,
    "incorrect": 26,
    "refused": 9
  }
}
```
