# judge-agreement: doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2-reasoning-high (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-26 23:46 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 0.940 | 0.890 to 0.980 |
| first_positive | 0.650 | 0.560 to 0.740 |
| second_positive | 0.610 | 0.510 to 0.710 |
| cohens_kappa | 0.881 | 0.777 to 0.962 |

## By question type

| Question type | Questions | agree | first_positive | second_positive |
|---|---|---|---|---|
| domain-relevant | 34 | 0.853 (0.74 to 0.97) | 0.588 (0.41 to 0.74) | 0.500 (0.32 to 0.68) |
| metrics-generated | 33 | 1.000 (1.00 to 1.00) | 0.879 (0.76 to 0.97) | 0.879 (0.76 to 0.97) |
| novel-generated | 33 | 0.970 (0.91 to 1.00) | 0.485 (0.30 to 0.67) | 0.455 (0.27 to 0.64) |

## System

```json
{
  "answers_run": "doc-agent-v4-full",
  "confusion": {
    "qwen3.8-27b-p2 correct, qwen-3.8-27b-p2-reasoning-high correct": 60,
    "qwen3.8-27b-p2 correct, qwen-3.8-27b-p2-reasoning-high incorrect": 5,
    "qwen3.8-27b-p2 incorrect, qwen-3.8-27b-p2-reasoning-high correct": 1,
    "qwen3.8-27b-p2 incorrect, qwen-3.8-27b-p2-reasoning-high incorrect": 28,
    "qwen3.8-27b-p2 refused, qwen-3.8-27b-p2-reasoning-high refused": 6
  },
  "disagreements": [
    "financebench_id_00684",
    "financebench_id_00685",
    "financebench_id_00288",
    "financebench_id_00678",
    "financebench_id_00790",
    "financebench_id_01163"
  ],
  "errors": {
    "qwen-3.8-27b-p2-reasoning-high": 9,
    "qwen3.8-27b-p2": 0
  },
  "first": "qwen3.8-27b-p2",
  "positive_difference_mcnemar_p": 0.2188,
  "second": "qwen-3.8-27b-p2-reasoning-high",
  "suite": "correctness"
}
```
