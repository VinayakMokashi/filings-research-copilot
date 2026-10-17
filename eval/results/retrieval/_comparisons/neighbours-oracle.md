# Neighbouring chunks, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-nb1-oracle` | 0.608 | 0.575 | -0.033 (-0.092 to +0.023) | 0.3128 | 0.3128 | no significant difference |
