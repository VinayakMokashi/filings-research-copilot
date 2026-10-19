# Context budget and split-page parts

context_hit on 100 paired dev questions against the baseline `page-rw-all-understood-b3000`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page-rw-all-understood-b1500` | 0.680 | 0.520 | -0.160 (-0.240 to -0.090) | 0.0002 | 0.0006 | worse |
| `page-rw-all-understood-b4500` | 0.680 | 0.730 | +0.050 (+0.010 to +0.100) | 0.0643 | 0.0643 | no significant difference |
| `page-rw-all-understood-b3000-siblings` | 0.680 | 0.610 | -0.070 (-0.120 to -0.020) | 0.0150 | 0.0300 | worse |
