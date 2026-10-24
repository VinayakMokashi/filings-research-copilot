# routing: keyword (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-24 15:22 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.650 | 0.533 to 0.767 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 6 | 0.667 (0.33 to 1.00) |
| data | 15 | 0.667 (0.40 to 0.87) |
| decline | 9 | 0.556 (0.22 to 0.89) |
| doc | 15 | 0.733 (0.53 to 0.93) |
| hybrid | 9 | 0.556 (0.22 to 0.89) |
| smalltalk | 6 | 0.667 (0.33 to 1.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 40 | 0.525 (0.38 to 0.68) |
| seed | 20 | 0.900 (0.75 to 1.00) |

## System

```json
{
  "baseline": "keyword"
}
```
