# correctness: doc-agent-v4-cerebras--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:58 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| correct | 0.650 | 0.550 to 0.740 |
| incorrect | 0.280 | 0.190 to 0.370 |
| refused | 0.070 | 0.020 to 0.120 |

## By question type

| Question type | Questions | correct | incorrect | refused |
|---|---|---|---|---|
| domain-relevant | 34 | 0.559 (0.38 to 0.74) | 0.382 (0.24 to 0.56) | 0.059 (0.00 to 0.15) |
| metrics-generated | 33 | 0.879 (0.76 to 0.97) | 0.091 (0.00 to 0.21) | 0.030 (0.00 to 0.09) |
| novel-generated | 33 | 0.515 (0.33 to 0.67) | 0.364 (0.21 to 0.52) | 0.121 (0.03 to 0.24) |

## System

```json
{
  "answers_run": "doc-agent-v4-cerebras",
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_prompt_version": "2",
  "judge_tokens": 67760,
  "verdicts": {
    "correct": 65,
    "incorrect": 28,
    "refused": 7
  }
}
```
