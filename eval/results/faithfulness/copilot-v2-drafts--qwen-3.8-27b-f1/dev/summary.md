# faithfulness: copilot-v2-drafts--qwen-3.8-27b-f1 (dev)

93 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 04:29 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.312 | 0.215 to 0.409 |
| supported_share | 0.449 | 0.362 to 0.537 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.375 (0.22 to 0.53) | 0.656 (0.54 to 0.77) |
| metrics-generated | 33 | 0.030 (0.00 to 0.09) | 0.030 (0.00 to 0.09) |
| novel-generated | 28 | 0.571 (0.39 to 0.75) | 0.704 (0.55 to 0.85) |

## System

```json
{
  "answers_run": "copilot-v2-drafts",
  "citation_precision": 0.9157,
  "citations": 178,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 84881,
  "prompt_version": "1"
}
```
