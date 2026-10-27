# correctness: copilot-v1-drafts--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:38 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.550 | 0.450 to 0.650 |
| incorrect | 0.310 | 0.220 to 0.400 |
| refused | 0.140 | 0.080 to 0.210 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.382 (0.24 to 0.56) | 0.441 (0.29 to 0.62) | 0.176 (0.06 to 0.32) |
| metrics-generated | 33 | 0.939 (0.85 to 1.00) | 0.061 (0.00 to 0.15) | 0.000 (0.00 to 0.00) |
| novel-generated | 33 | 0.333 (0.18 to 0.48) | 0.424 (0.27 to 0.61) | 0.242 (0.12 to 0.39) |

## System

```json
{
  "answers_run": "copilot-v1-drafts",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 62048,
  "verdicts": {
    "correct": 55,
    "incorrect": 31,
    "refused": 14
  }
}
```
