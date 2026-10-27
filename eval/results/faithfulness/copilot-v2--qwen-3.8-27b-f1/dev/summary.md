# faithfulness: copilot-v2--qwen-3.8-27b-f1 (dev)

91 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 04:29 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.495 | 0.396 to 0.593 |
| supported_share | 0.539 | 0.440 to 0.639 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 31 | 0.774 (0.61 to 0.90) | 0.858 (0.74 to 0.95) |
| metrics-generated | 33 | 0.030 (0.00 to 0.09) | 0.030 (0.00 to 0.09) |
| novel-generated | 27 | 0.741 (0.56 to 0.89) | 0.795 (0.65 to 0.93) |

## System

```json
{
  "answers_run": "copilot-v2",
  "citation_precision": 0.963,
  "citations": 189,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 79812,
  "prompt_version": "1"
}
```
