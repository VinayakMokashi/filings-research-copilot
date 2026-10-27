# cascade-classifier-v2 (dev): the first router's route above a confidence threshold

First `classifier-v2`, second `llm-gpt-oss-120b`, 138 questions; 95% bootstrap intervals.

| Threshold | Accuracy | Sent on | Errors | Median latency | Cost a question |
|---|---|---|---|---|---|
| 0.5 | 0.920 (0.877 to 0.964) | 1% | 11 | 8 ms | $0.000002 |
| 0.7 | 0.942 (0.899 to 0.978) | 5% | 8 | 8 ms | $0.000010 |
| 0.8 | 0.957 (0.920 to 0.986) | 9% | 6 | 8 ms | $0.000017 |
| 0.9 | 0.957 (0.920 to 0.986) | 13% | 6 | 8 ms | $0.000025 |
| 0.95 | 0.957 (0.920 to 0.986) | 17% | 6 | 8 ms | $0.000033 |
| 0.98 | 0.964 (0.927 to 0.993) | 22% | 5 | 8 ms | $0.000044 |
| 0.99 | 0.978 (0.949 to 1.000) | 36% | 3 | 9 ms | $0.000069 |
