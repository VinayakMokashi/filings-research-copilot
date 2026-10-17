# Search mode, whole corpus

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 2 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-bm25-corpus` | 0.345 | 0.155 | -0.190 (-0.280 to -0.095) | 0.0003 | 0.0006 | worse |
| `tokens-480_bge-small-hybrid-corpus` | 0.345 | 0.210 | -0.135 (-0.225 to -0.045) | 0.0071 | 0.0071 | worse |
