# Query understanding against the oracle document

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-understood` | 0.630 | 0.570 | -0.060 (-0.110 to -0.020) | 0.0311 | 0.0311 | worse |
