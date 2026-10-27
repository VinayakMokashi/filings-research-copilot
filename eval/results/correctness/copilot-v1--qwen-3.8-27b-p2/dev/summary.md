# correctness: copilot-v1--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:34 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.490 | 0.390 to 0.590 |
| incorrect | 0.330 | 0.240 to 0.420 |
| refused | 0.180 | 0.110 to 0.260 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.235 (0.09 to 0.38) | 0.500 (0.32 to 0.68) | 0.265 (0.12 to 0.41) |
| metrics-generated | 33 | 0.939 (0.85 to 1.00) | 0.061 (0.00 to 0.15) | 0.000 (0.00 to 0.00) |
| novel-generated | 33 | 0.303 (0.15 to 0.45) | 0.424 (0.27 to 0.61) | 0.273 (0.12 to 0.42) |

## System

```json
{
  "answers_run": "copilot-v1",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 58534,
  "verdicts": {
    "correct": 49,
    "incorrect": 33,
    "refused": 18
  }
}
```
