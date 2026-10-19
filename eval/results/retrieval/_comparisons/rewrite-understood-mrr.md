# Query rewriting, resolved filings

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-understood`; paired permutation tests, Holm-adjusted across 4 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-rw-multi-understood` | 0.381 | 0.454 | +0.072 (+0.010 to +0.136) | 0.0271 | 0.0813 | no significant difference |
| `page_bge-small-dense-rw-hyde-understood` | 0.381 | 0.388 | +0.007 (-0.048 to +0.057) | 0.8026 | 0.8026 | no significant difference |
| `page_bge-small-dense-rw-decompose-understood` | 0.381 | 0.415 | +0.034 (-0.021 to +0.089) | 0.2351 | 0.4702 | no significant difference |
| `page_bge-small-dense-rw-multi-hyde-decompose-understood` | 0.381 | 0.476 | +0.095 (+0.031 to +0.160) | 0.0044 | 0.0176 | better |
