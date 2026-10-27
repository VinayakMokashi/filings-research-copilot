# Answer arms against gpt-oss-120b at its default effort

correct on 100 paired dev questions against the baseline `arm-strong--qwen-3.8-27b-p2`; paired permutation tests, Holm-adjusted across 2 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `arm-strong-low--qwen-3.8-27b-p2` | 0.650 | 0.630 | -0.020 (-0.070 to +0.030) | 0.6929 | 0.8559 | no significant difference |
| `arm-fast--qwen-3.8-27b-p2` | 0.650 | 0.610 | -0.040 (-0.110 to +0.030) | 0.4280 | 0.8559 | no significant difference |
