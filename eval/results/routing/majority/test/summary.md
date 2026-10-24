# routing: majority (test)

60 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-24 15:22 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| accuracy | 0.250 | 0.150 to 0.367 |

## By route

| Route | Questions | accuracy |
|---|---|---|
| brief | 6 | 0.000 (0.00 to 0.00) |
| data | 15 | 0.000 (0.00 to 0.00) |
| decline | 9 | 0.000 (0.00 to 0.00) |
| doc | 15 | 1.000 (1.00 to 1.00) |
| hybrid | 9 | 0.000 (0.00 to 0.00) |
| smalltalk | 6 | 0.000 (0.00 to 0.00) |

## By origin

| Origin | Questions | accuracy |
|---|---|---|
| paraphrase | 40 | 0.250 (0.12 to 0.40) |
| seed | 20 | 0.250 (0.10 to 0.45) |

## System

```json
{
  "baseline": "majority",
  "route": "doc"
}
```
