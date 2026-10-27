# Domain embedder, corpus, mrr@10

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-corpus` | 0.230 | 0.231 | +0.001 (-0.000 to +0.003) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-corpus` | 0.230 | 0.134 | -0.096 (-0.160 to -0.036) | 0.0023 | 0.0069 | worse |
| `page_embedder-v2-dense-corpus` | 0.230 | 0.162 | -0.068 (-0.131 to -0.006) | 0.0364 | 0.0728 | no significant difference |
