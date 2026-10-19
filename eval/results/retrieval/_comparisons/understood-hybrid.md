# Hybrid search with query understanding

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-understood`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-hybrid-understood` | 0.570 | 0.525 | -0.045 (-0.115 to +0.020) | 0.2387 | 0.2387 | no significant difference |
