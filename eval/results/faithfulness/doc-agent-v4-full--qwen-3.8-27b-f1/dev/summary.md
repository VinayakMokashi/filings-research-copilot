# faithfulness: doc-agent-v4-full--qwen-3.8-27b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 23:43 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| faithful | 0.617 | 0.521 to 0.713 |
| supported_share | 0.762 | 0.690 to 0.831 |

## By question type

| Question type | Questions | faithful | supported_share |
|---|---|---|---|
| domain-relevant | 32 | 0.375 (0.22 to 0.53) | 0.677 (0.57 to 0.78) |
| metrics-generated | 31 | 0.871 (0.74 to 0.97) | 0.909 (0.81 to 0.99) |
| novel-generated | 31 | 0.613 (0.45 to 0.77) | 0.704 (0.56 to 0.84) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "citation_precision": 0.9612,
  "citations": 258,
  "judge_errors": 0,
  "judge_model": "cerebras/qwen-3.8-27b",
  "judge_tokens": 136749,
  "prompt_version": "1"
}
```
