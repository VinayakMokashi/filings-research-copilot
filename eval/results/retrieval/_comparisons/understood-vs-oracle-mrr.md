# Query understanding against the oracle document

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-understood` | 0.423 | 0.381 | -0.041 (-0.066 to -0.021) | 0.0001 | 0.0001 | worse |
