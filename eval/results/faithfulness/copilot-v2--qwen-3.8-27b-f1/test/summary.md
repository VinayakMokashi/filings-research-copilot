# faithfulness: copilot-v2--qwen-3.8-27b-f1 (test)

47 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:46 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.447 | 0.298 to 0.596 |
| supported_share | 0.530 | 0.394 to 0.665 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 16 | 0.625 (0.38 to 0.88) | 0.797 (0.61 to 0.94) |
| metrics-generated | 17 | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) |
| novel-generated | 14 | 0.786 (0.57 to 1.00) | 0.869 (0.70 to 1.00) |

## System

```json
{
  "answers_run": "copilot-v2",
  "citation_precision": 0.9831,
  "citations": 59,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 35679,
  "prompt_version": "1"
}
```
