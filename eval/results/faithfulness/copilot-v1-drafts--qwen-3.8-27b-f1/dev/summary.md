# faithfulness: copilot-v1-drafts--qwen-3.8-27b-f1 (dev)

86 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:40 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.244 | 0.151 to 0.337 |
| supported_share | 0.376 | 0.289 to 0.463 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 28 | 0.321 (0.14 to 0.50) | 0.649 (0.54 to 0.76) |
| metrics-generated | 33 | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) |
| novel-generated | 25 | 0.480 (0.28 to 0.68) | 0.567 (0.39 to 0.74) |

## System

```json
{
  "answers_run": "copilot-v1-drafts",
  "citation_precision": 0.9007,
  "citations": 141,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 69856,
  "prompt_version": "1"
}
```
