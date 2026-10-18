# Chunking, dense search, whole corpus

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-corpus` | 0.345 | 0.415 | +0.070 (-0.010 to +0.155) | 0.1100 | 0.1100 | no significant difference |
