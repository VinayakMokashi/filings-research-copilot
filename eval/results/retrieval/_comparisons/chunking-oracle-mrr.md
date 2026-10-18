# Chunking, dense search, oracle document (MRR@10)

mrr@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-oracle` | 0.307 | 0.423 | +0.115 (+0.048 to +0.184) | 0.0010 | 0.0030 | better |
| `tokens-256_bge-small-dense-oracle` | 0.307 | 0.377 | +0.070 (+0.011 to +0.128) | 0.0184 | 0.0368 | better |
| `semantic_bge-small-dense-oracle` | 0.307 | 0.364 | +0.057 (-0.008 to +0.122) | 0.0952 | 0.0952 | no significant difference |
