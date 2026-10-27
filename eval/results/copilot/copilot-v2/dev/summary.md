# copilot: copilot-v2 (dev)

100 questions, 95% bootstrap intervals (10,000 resamples), 2026-10-27 04:25 UTC

| Metric | Mean | 95% interval |
|---|---|---|
| answered | 0.910 | 0.850 to 0.960 |
| tool_ok | 1.000 | 1.000 to 1.000 |
| handed_on | 0.040 | 0.010 to 0.080 |
| revised | 0.280 | 0.190 to 0.370 |
| steps | 8.760 | 8.520 to 9.010 |
| cost_usd | 0.005 | 0.005 to 0.005 |
| seconds | 14.157 | 10.112 to 19.556 |

## By route

| Route | Questions | answered | tool_ok | handed_on | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|
| data | 40 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.100 (0.03 to 0.20) | 0.025 (0.00 to 0.07) | 8.150 (8.03 to 8.32) | 0.004 (0.00 to 0.00) | 5.139 (3.97 to 6.79) |
| decline | 1 | 0.000 (0.00 to 0.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.000 (0.00 to 0.00) | 8.000 (8.00 to 8.00) | 0.001 (0.00 to 0.00) | 3.660 (3.66 to 3.66) |
| doc | 36 | 0.806 (0.67 to 0.92) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.306 (0.17 to 0.44) | 8.889 (8.44 to 9.39) | 0.005 (0.00 to 0.01) | 13.116 (8.78 to 18.08) |
| hybrid | 23 | 0.957 (0.87 to 1.00) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.696 (0.52 to 0.87) | 9.652 (9.13 to 10.17) | 0.007 (0.01 to 0.01) | 31.924 (18.84 to 51.78) |

## By question type

| Question type | Questions | answered | tool_ok | handed_on | revised | steps | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|
| domain-relevant | 34 | 0.912 (0.79 to 1.00) | 1.000 (1.00 to 1.00) | 0.088 (0.00 to 0.21) | 0.618 (0.44 to 0.76) | 9.559 (9.12 to 10.00) | 0.006 (0.01 to 0.01) | 25.586 (16.17 to 39.72) |
| metrics-generated | 33 | 1.000 (1.00 to 1.00) | 1.000 (1.00 to 1.00) | 0.030 (0.00 to 0.09) | 0.000 (0.00 to 0.00) | 8.030 (8.00 to 8.09) | 0.004 (0.00 to 0.00) | 3.892 (3.64 to 4.26) |
| novel-generated | 33 | 0.818 (0.70 to 0.94) | 1.000 (1.00 to 1.00) | 0.000 (0.00 to 0.00) | 0.212 (0.09 to 0.36) | 8.667 (8.24 to 9.15) | 0.005 (0.00 to 0.01) | 12.645 (7.80 to 18.13) |

## System

```json
{
  "graph": "rewrite, understand, route, specialist (data on to doc when it finds nothing), synthesise, validate, respond, remember",
  "median_seconds": 4.0,
  "router_fallbacks": 0,
  "routes": {
    "data": 40,
    "decline": 1,
    "doc": 36,
    "hybrid": 23
  }
}
```
