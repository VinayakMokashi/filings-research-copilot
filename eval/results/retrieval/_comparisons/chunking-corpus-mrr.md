# Chunking, dense search, whole corpus (MRR@10)

mrr@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-corpus` | 0.115 | 0.230 | +0.115 (+0.065 to +0.170) | 0.0001 | 0.0001 | better |
