# cascade-classifier-v1 (dev): the first router's route above a confidence threshold

First `classifier-v1`, second `llm-gpt-oss-120b`, 138 questions; 95% bootstrap intervals.

| Threshold | Accuracy | Sent on | Errors | Median latency | Cost a question |
|---|---|---|---|---|---|
| 0.9 | 0.891 (0.833 to 0.942) | 7% | 15 | 9 ms | $0.000015 |
| 0.95 | 0.906 (0.855 to 0.949) | 12% | 13 | 10 ms | $0.000023 |
| 0.98 | 0.935 (0.891 to 0.971) | 20% | 9 | 10 ms | $0.000038 |
| 0.99 | 0.978 (0.949 to 1.000) | 33% | 3 | 11 ms | $0.000063 |
| 0.995 | 1.000 (1.000 to 1.000) | 52% | 0 | 340 ms | $0.000100 |
