# All rewrites against multi-query

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-rw-multi-understood`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-rw-multi-hyde-decompose-understood` | 0.682 | 0.722 | +0.040 (+0.005 to +0.085) | 0.0936 | 0.0936 | no significant difference |
