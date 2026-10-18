# Late chunking, jina-v2-small, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_jina-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-late-dense-oracle` | 0.593 | 0.613 | +0.020 (-0.050 to +0.090) | 0.6796 | 0.6796 | no significant difference |
