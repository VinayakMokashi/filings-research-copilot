# judge-agreement: doc-agent-v3-full--gpt-oss-20b-p2 (dev)

41 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-22 20:45 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| agree | 0.927 | 0.829 to 1.000 |
| labeller_correct | 0.707 | 0.561 to 0.829 |
| judge_correct | 0.634 | 0.488 to 0.780 |
| cohens_kappa | 0.835 | 0.631 to 1.000 |

## By question type

| Question type | Questions | agree | labeller_correct | judge_correct |
|---|---|---|---|---|
| domain-relevant | 13 | 0.769 (0.54 to 1.00) | 0.769 (0.54 to 1.00) | 0.538 (0.31 to 0.77) |
| metrics-generated | 14 | 1.000 (1.00 to 1.00) | 0.929 (0.79 to 1.00) | 0.929 (0.79 to 1.00) |
| novel-generated | 14 | 1.000 (1.00 to 1.00) | 0.429 (0.21 to 0.71) | 0.429 (0.21 to 0.71) |

## System

```json
{
  "answers_run": "doc-agent-v3-full",
  "confusion": {
    "labeller correct, judge correct": 26,
    "labeller correct, judge incorrect": 3,
    "labeller incorrect, judge incorrect": 12
  },
  "judge": "gpt-oss-20b-p2",
  "labelled": 41,
  "labellers": [
    "claude"
  ]
}
```
