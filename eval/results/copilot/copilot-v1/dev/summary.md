# copilot: copilot-v1 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 01:29 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.820 | 0.740 to 0.890 |
| tool_ok | 1.000 | 1.000 to 1.000 |
| revised | 0.260 | 0.180 to 0.350 |
| steps | 8.740 | 8.480 to 9.020 |
| cost_usd | 0.005 | 0.004 to 0.005 |
| seconds | 33.364 | 28.901 to 38.076 |

## By route

| Route | Questions | answered | tool_ok | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|
| data | 47 | 0.851 (0.74 to 0.94) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 8.000 (8.00 to 8.00) | 0.004 (0.00 to 0.00) | 16.319 (14.76 to 17.78) |
| decline | 2 | 0.000 (0.00 to 0.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 8.000 (8.00 to 8.00) | 0.000 (0.00 to 0.00) | 3.675 (3.60 to 3.75) |
| doc | 31 | 0.774 (0.61 to 0.90) | 1.000 (1.00 to 1.00) | 0.387 (0.23 to 0.55) | 9.032 (8.58 to 9.55) | 0.005 (0.00 to 0.01) | 42.888 (38.15 to 48.15) |
| hybrid | 20 | 0.900 (0.75 to 1.00) | 1.000 (1.00 to 1.00) | 0.700 (0.50 to 0.90) | 10.100 (9.40 to 10.80) | 0.008 (0.01 to 0.01) | 61.629 (50.76 to 74.03) |

## By question type

| Question type | Questions | answered | tool_ok | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.735 (0.59 to 0.88) | 1.000 (1.00 to 1.00) | 0.588 (0.41 to 0.74) | 9.647 (9.12 to 10.18) | 0.006 (0.01 to 0.01) | 50.866 (41.72 to 60.33) |
| metrics-generated | 33 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 8.000 (8.00 to 8.00) | 0.004 (0.00 to 0.00) | 16.978 (15.30 to 18.23) |
| novel-generated | 33 | 0.727 (0.58 to 0.88) | 1.000 (1.00 to 1.00) | 0.182 (0.06 to 0.33) | 8.545 (8.18 to 8.97) | 0.004 (0.00 to 0.00) | 31.718 (26.25 to 37.50) |

## System

```json
{
  "graph": "rewrite, understand, route, specialist, synthesise, validate, respond, remember",
  "median_seconds": 28.5,
  "router_fallbacks": 0,
  "routes": {
    "data": 47,
    "decline": 2,
    "doc": 31,
    "hybrid": 20
  }
}
```
