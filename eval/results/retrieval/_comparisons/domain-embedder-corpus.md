# Domain embedder, corpus, recall@10

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-corpus` | 0.415 | 0.415 | +0.000 (+0.000 to +0.000) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-corpus` | 0.415 | 0.280 | -0.135 (-0.235 to -0.040) | 0.0093 | 0.0279 | worse |
| `page_embedder-v2-dense-corpus` | 0.415 | 0.335 | -0.080 (-0.175 to +0.010) | 0.1112 | 0.2224 | no significant difference |
