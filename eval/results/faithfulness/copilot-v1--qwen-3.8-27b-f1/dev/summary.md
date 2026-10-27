# faithfulness: copilot-v1--qwen-3.8-27b-f1 (dev)

82 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:37 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.390 | 0.280 to 0.500 |
| supported_share | 0.427 | 0.323 to 0.530 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 25 | 0.680 (0.48 to 0.84) | 0.800 (0.66 to 0.93) |
| metrics-generated | 33 | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) |
| novel-generated | 24 | 0.625 (0.42 to 0.79) | 0.625 (0.42 to 0.79) |

## System

```json
{
  "answers_run": "copilot-v1",
  "citation_precision": 0.9912,
  "citations": 114,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 60883,
  "prompt_version": "1"
}
```
