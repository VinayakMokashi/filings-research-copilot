# correctness: arm-fast--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 22:24 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.610 | 0.510 to 0.700 |
| incorrect | 0.230 | 0.150 to 0.310 |
| refused | 0.160 | 0.090 to 0.230 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.382 (0.24 to 0.56) | 0.412 (0.26 to 0.59) | 0.206 (0.09 to 0.35) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.061 (0.00 to 0.15) | 0.061 (0.00 to 0.15) |
| novel-generated | 33 | 0.576 (0.39 to 0.73) | 0.212 (0.09 to 0.36) | 0.212 (0.09 to 0.36) |

## System

```json
{
  "answers_run": "arm-fast",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 60554,
  "verdicts": {
    "correct": 61,
    "incorrect": 23,
    "refused": 16
  }
}
```
