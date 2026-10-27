# correctness: copilot-v2-drafts--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 04:29 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.670 | 0.580 to 0.760 |
| incorrect | 0.260 | 0.170 to 0.350 |
| refused | 0.070 | 0.020 to 0.120 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.529 (0.35 to 0.71) | 0.412 (0.26 to 0.59) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.970 (0.91 to 1.00) | 0.030 (0.00 to 0.09) | 0.000 (0.00 to 0.00) |
| novel-generated | 33 | 0.515 (0.33 to 0.67) | 0.333 (0.18 to 0.48) | 0.152 (0.03 to 0.27) |

## System

```json
{
  "answers_run": "copilot-v2-drafts",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 67109,
  "verdicts": {
    "correct": 67,
    "incorrect": 26,
    "refused": 7
  }
}
```
