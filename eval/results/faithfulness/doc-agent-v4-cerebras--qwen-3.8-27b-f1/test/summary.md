# faithfulness: doc-agent-v4-cerebras--qwen-3.8-27b-f1 (test)

48 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:46 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.625 | 0.479 to 0.750 |
| supported_share | 0.773 | 0.675 to 0.863 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 16 | 0.500 (0.25 to 0.75) | 0.745 (0.59 to 0.89) |
| metrics-generated | 15 | 0.933 (0.80 to 1.00) | 0.978 (0.93 to 1.00) |
| novel-generated | 17 | 0.471 (0.24 to 0.71) | 0.618 (0.41 to 0.79) |

## System

```json
{
  "answers_run": "doc-agent-v4-cerebras",
  "citation_precision": 0.93,
  "citations": 100,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 65707,
  "prompt_version": "1"
}
```
