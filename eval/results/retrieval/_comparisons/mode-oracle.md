# Search mode, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-oracle` | 0.608 | 0.440 | -0.168 (-0.263 to -0.075) | 0.0007 | 0.0021 | worse |
| `tokens-480_bge-small-hybrid-oracle` | 0.608 | 0.540 | -0.068 (-0.145 to +0.008) | 0.1021 | 0.1820 | no significant difference |
| `tokens-480_bge-small-hybrid-w2-1-oracle` | 0.608 | 0.540 | -0.068 (-0.142 to +0.005) | 0.0910 | 0.1820 | no significant difference |
