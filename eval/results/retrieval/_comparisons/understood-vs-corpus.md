# Query understanding against the whole corpus

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-understood` | 0.415 | 0.570 | +0.155 (+0.090 to +0.225) | 0.0001 | 0.0001 | better |
