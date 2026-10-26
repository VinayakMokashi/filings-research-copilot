# judge-agreement: doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1 (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 23:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 0.968 | 0.926 to 1.000 |
| first_positive | 0.628 | 0.532 to 0.723 |
| second_positive | 0.617 | 0.521 to 0.713 |
| cohens_kappa | 0.932 | 0.845 to 1.000 |

## By question type

| Question type | Questions | agree | first_positive | second_positive |
|---|---|---|---|---|
| domain-relevant | 32 | 0.969 (0.91 to 1.00) | 0.406 (0.25 to 0.56) | 0.375 (0.22 to 0.53) |
| metrics-generated | 31 | 1.000 (1.00 to 1.00) | 0.871 (0.74 to 0.97) | 0.871 (0.74 to 0.97) |
| novel-generated | 31 | 0.935 (0.84 to 1.00) | 0.613 (0.45 to 0.77) | 0.613 (0.45 to 0.77) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "confusion": {
    "qwen3.8-27b-f1 False, qwen-3.8-27b-f1 False": 34,
    "qwen3.8-27b-f1 False, qwen-3.8-27b-f1 True": 1,
    "qwen3.8-27b-f1 True, qwen-3.8-27b-f1 False": 2,
    "qwen3.8-27b-f1 True, qwen-3.8-27b-f1 True": 57
  },
  "disagreements": [
    "financebench_id_01226",
    "financebench_id_01858",
    "financebench_id_01912"
  ],
  "errors": {
    "qwen-3.8-27b-f1": 0,
    "qwen3.8-27b-f1": 0
  },
  "first": "qwen3.8-27b-f1",
  "positive_difference_mcnemar_p": 1.0,
  "second": "qwen-3.8-27b-f1",
  "suite": "faithfulness"
}
```
