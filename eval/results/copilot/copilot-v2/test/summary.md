# copilot: copilot-v2 (test)

50 questions, 95% bootstrap intervals (10,000 resamples), 2026-11-25 07:44 UTC. The held-out test split was opened for this run.

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.940 | 0.860 to 1.000 |
| tool_ok | 1.000 | 1.000 to 1.000 |
| handed_on | 0.020 | 0.000 to 0.060 |
| revised | 0.260 | 0.140 to 0.380 |
| steps | 8.620 | 8.340 to 8.920 |
| cost_usd | 0.005 | 0.004 to 0.005 |
| seconds | 29.457 | 23.607 to 35.736 |

## By route

| Route | Questions | answered | tool_ok | handed_on | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|
| data | 20 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.050 (0.00 to 0.15) | 0.000 (0.00 to 0.00) | 8.050 (8.00 to 8.15) | 0.004 (0.00 to 0.00) | 20.060 (18.81 to 22.12) |
| doc | 20 | 0.900 (0.75 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.350 (0.15 to 0.55) | 8.900 (8.40 to 9.50) | 0.005 (0.00 to 0.01) | 30.556 (19.11 to 44.13) |
| hybrid | 10 | 0.900 (0.70 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.600 (0.30 to 0.90) | 9.200 (8.60 to 9.80) | 0.006 (0.01 to 0.01) | 46.053 (34.88 to 56.27) |

## By question type

| Question type | Questions | answered | tool_ok | handed_on | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 16 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.062 (0.00 to 0.19) | 0.375 (0.12 to 0.62) | 8.812 (8.38 to 9.25) | 0.005 (0.00 to 0.01) | 36.379 (24.53 to 49.51) |
| metrics-generated | 17 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 8.000 (8.00 to 8.00) | 0.004 (0.00 to 0.00) | 19.181 (18.67 to 19.75) |
| novel-generated | 17 | 0.824 (0.65 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.412 (0.18 to 0.65) | 9.059 (8.47 to 9.76) | 0.005 (0.00 to 0.01) | 33.218 (22.28 to 46.52) |

## System

```json
{
  "graph": "rewrite, understand, route, specialist (data on to doc when it finds nothing), synthesise, validate, respond, remember",
  "median_seconds": 19.43,
  "router_fallbacks": 0,
  "routes": {
    "data": 20,
    "doc": 20,
    "hybrid": 10
  }
}
```
