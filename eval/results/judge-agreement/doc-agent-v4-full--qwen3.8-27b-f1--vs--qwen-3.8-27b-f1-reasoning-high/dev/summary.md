# judge-agreement: doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1-reasoning-high (dev)

94 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 23:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 0.830 | 0.755 to 0.904 |
| first_positive | 0.628 | 0.532 to 0.723 |
| second_positive | 0.521 | 0.415 to 0.617 |
| cohens_kappa | 0.656 | 0.497 to 0.805 |

## By question type

| Question type | Questions | agree | first_positive | second_positive |
|---|---|---|---|---|
| domain-relevant | 32 | 0.812 (0.69 to 0.94) | 0.406 (0.25 to 0.56) | 0.219 (0.09 to 0.38) |
| metrics-generated | 31 | 0.968 (0.90 to 1.00) | 0.871 (0.74 to 0.97) | 0.903 (0.81 to 1.00) |
| novel-generated | 31 | 0.710 (0.55 to 0.87) | 0.613 (0.45 to 0.77) | 0.452 (0.29 to 0.65) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "confusion": {
    "qwen3.8-27b-f1 False, qwen-3.8-27b-f1-reasoning-high False": 32,
    "qwen3.8-27b-f1 False, qwen-3.8-27b-f1-reasoning-high True": 3,
    "qwen3.8-27b-f1 True, qwen-3.8-27b-f1-reasoning-high False": 13,
    "qwen3.8-27b-f1 True, qwen-3.8-27b-f1-reasoning-high True": 46
  },
  "disagreements": [
    "financebench_id_01226",
    "financebench_id_00807",
    "financebench_id_01858",
    "financebench_id_00799",
    "financebench_id_01936",
    "financebench_id_01928",
    "financebench_id_01981",
    "financebench_id_00288",
    "financebench_id_01902",
    "financebench_id_04854",
    "financebench_id_00651",
    "financebench_id_01490",
    "financebench_id_00206",
    "financebench_id_01254",
    "financebench_id_01912",
    "financebench_id_00215"
  ],
  "errors": {
    "qwen-3.8-27b-f1-reasoning-high": 31,
    "qwen3.8-27b-f1": 0
  },
  "first": "qwen3.8-27b-f1",
  "positive_difference_mcnemar_p": 0.0213,
  "second": "qwen-3.8-27b-f1-reasoning-high",
  "suite": "faithfulness"
}
```
