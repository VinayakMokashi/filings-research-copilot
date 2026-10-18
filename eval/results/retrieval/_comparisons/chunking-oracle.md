# Chunking, dense search, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-oracle` | 0.608 | 0.630 | +0.022 (-0.043 to +0.088) | 0.5573 | 1.0000 | no significant difference |
| `tokens-256_bge-small-dense-oracle` | 0.608 | 0.640 | +0.032 (-0.040 to +0.105) | 0.4225 | 1.0000 | no significant difference |
| `semantic_bge-small-dense-oracle` | 0.608 | 0.610 | +0.002 (-0.063 to +0.070) | 1.0000 | 1.0000 | no significant difference |
