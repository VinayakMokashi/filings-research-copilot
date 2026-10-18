# Embedding model, tokens-480, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 1 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_jina-small-dense-oracle` | 0.608 | 0.593 | -0.015 (-0.095 to +0.060) | 0.8057 | 0.8057 | no significant difference |
