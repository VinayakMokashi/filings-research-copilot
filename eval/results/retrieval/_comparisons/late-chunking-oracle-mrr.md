# Late chunking, jina-v2-small, oracle document (MRR@10)

mrr@10 on 100 paired dev questions against the baseline `tokens-480_jina-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-late-dense-oracle` | 0.337 | 0.328 | -0.009 (-0.068 to +0.048) | 0.7537 | 0.7537 | no significant difference |
