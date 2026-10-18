# Page chunks: search mode, whole corpus

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 2 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-corpus` | 0.415 | 0.185 | -0.230 (-0.335 to -0.125) | 0.0002 | 0.0004 | worse |
| `page_bge-small-hybrid-corpus` | 0.415 | 0.315 | -0.100 (-0.180 to -0.020) | 0.0206 | 0.0206 | worse |
