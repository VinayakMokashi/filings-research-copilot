# judge-agreement: doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 23:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 0.990 | 0.970 to 1.000 |
| first_positive | 0.650 | 0.560 to 0.740 |
| second_positive | 0.640 | 0.550 to 0.730 |
| cohens_kappa | 0.980 | 0.933 to 1.000 |

## By question type

| Question type | Questions | agree | first_positive | second_positive |
|---|---|---|---|---|
| domain-relevant | 34 | 0.971 (0.91 to 1.00) | 0.588 (0.41 to 0.74) | 0.559 (0.38 to 0.74) |
| metrics-generated | 33 | 1.000 (1.00 to 1.00) | 0.879 (0.76 to 0.97) | 0.879 (0.76 to 0.97) |
| novel-generated | 33 | 1.000 (1.00 to 1.00) | 0.485 (0.30 to 0.67) | 0.485 (0.30 to 0.67) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "confusion": {
    "qwen3.8-27b-p2 correct, qwen-3.8-27b-p2 correct": 64,
    "qwen3.8-27b-p2 correct, qwen-3.8-27b-p2 incorrect": 1,
    "qwen3.8-27b-p2 incorrect, qwen-3.8-27b-p2 incorrect": 29,
    "qwen3.8-27b-p2 refused, qwen-3.8-27b-p2 refused": 6
  },
  "disagreements": [
    "financebench_id_00684"
  ],
  "errors": {
    "qwen-3.8-27b-p2": 0,
    "qwen3.8-27b-p2": 0
  },
  "first": "qwen3.8-27b-p2",
  "positive_difference_mcnemar_p": 1.0,
  "second": "qwen-3.8-27b-p2",
  "suite": "correctness"
}
```
