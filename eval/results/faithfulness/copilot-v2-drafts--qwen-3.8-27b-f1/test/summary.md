# faithfulness: copilot-v2-drafts--qwen-3.8-27b-f1 (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:47 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.340 | 0.220 to 0.480 |
| supported_share | 0.445 | 0.322 to 0.568 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 16 | 0.500 (0.25 to 0.75) | 0.703 (0.52 to 0.86) |
| metrics-generated | 17 | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) |
| novel-generated | 17 | 0.529 (0.29 to 0.76) | 0.647 (0.44 to 0.82) |

## System

```json
{
  "answers_run": "copilot-v2-drafts",
  "citation_precision": 0.9118,
  "citations": 68,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 40937,
  "prompt_version": "1"
}
```
