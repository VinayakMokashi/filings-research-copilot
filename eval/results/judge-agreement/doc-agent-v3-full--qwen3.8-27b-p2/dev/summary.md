# judge-agreement: doc-agent-v3-full--qwen3.8-27b-p2 (dev)

41 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-22 20:45 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 1.000 | 1.000 to 1.000 |
| labeller_correct | 0.707 | 0.561 to 0.829 |
| judge_correct | 0.707 | 0.561 to 0.829 |
| cohens_kappa | 1.000 | 1.000 to 1.000 |

## By question type

| Question type | Questions | agree | labeller_correct | judge_correct |
|---|---|---|---|---|
| domain-relevant | 13 | 1.000 (1.00 to 1.00) | 0.769 (0.54 to 1.00) | 0.769 (0.54 to 1.00) |
| metrics-generated | 14 | 1.000 (1.00 to 1.00) | 0.929 (0.79 to 1.00) | 0.929 (0.79 to 1.00) |
| novel-generated | 14 | 1.000 (1.00 to 1.00) | 0.429 (0.21 to 0.71) | 0.429 (0.21 to 0.71) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "confusion": {
    "labeller correct, judge correct": 29,
    "labeller incorrect, judge incorrect": 12
  },
  "judge": "qwen3.8-27b-p2",
  "labelled": 41,
  "labellers": [
    "claude"
  ]
}
```
