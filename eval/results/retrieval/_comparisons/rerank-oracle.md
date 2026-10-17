# Reranking, oracle document

recall@10 on 100 paired dev questions against the baseline `tokens-480_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `tokens-480_bge-small-dense-rerank-minilm-l6-oracle` | 0.608 | 0.510 | -0.098 (-0.185 to -0.013) | 0.0326 | 0.0978 | no significant difference |
| `tokens-480_bge-small-dense-rerank-jina-turbo-oracle` | 0.608 | 0.580 | -0.028 (-0.113 to +0.057) | 0.5664 | 1.0000 | no significant difference |
| `tokens-480_bge-small-dense-rerank-bge-base-oracle` | 0.608 | 0.605 | -0.003 (-0.072 to +0.060) | 1.0000 | 1.0000 | no significant difference |
