# Query understanding against the whole corpus

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-corpus`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-understood` | 0.230 | 0.381 | +0.151 (+0.104 to +0.203) | 0.0001 | 0.0001 | better |
