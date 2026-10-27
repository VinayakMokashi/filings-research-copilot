# faithfulness: doc-agent-v4-cerebras--qwen-3.8-27b-f1 (dev)

93 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 02:01 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.624 | 0.527 to 0.720 |
| supported_share | 0.790 | 0.726 to 0.851 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.344 (0.19 to 0.50) | 0.677 (0.58 to 0.77) |
| metrics-generated | 32 | 0.938 (0.84 to 1.00) | 0.958 (0.89 to 1.00) |
| novel-generated | 29 | 0.586 (0.41 to 0.76) | 0.730 (0.59 to 0.86) |

## System

```json
{
  "answers_run": "doc-agent-v4-cerebras",
  "citation_precision": 0.9447,
  "citations": 253,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 138204,
  "prompt_version": "1"
}
```
