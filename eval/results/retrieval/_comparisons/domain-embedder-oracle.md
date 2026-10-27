# Domain embedder, oracle, recall@10

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-oracle` | 0.630 | 0.630 | +0.000 (+0.000 to +0.000) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-oracle` | 0.630 | 0.660 | +0.030 (-0.035 to +0.095) | 0.4663 | 1.0000 | no significant difference |
| `page_embedder-v2-dense-oracle` | 0.630 | 0.645 | +0.015 (-0.045 to +0.075) | 0.7525 | 1.0000 | no significant difference |
