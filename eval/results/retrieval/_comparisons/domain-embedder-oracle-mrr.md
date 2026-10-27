# Domain embedder, oracle, mrr@10

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-oracle` | 0.423 | 0.423 | +0.000 (+0.000 to +0.000) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-oracle` | 0.423 | 0.373 | -0.049 (-0.112 to +0.012) | 0.1250 | 0.3666 | no significant difference |
| `page_embedder-v2-dense-oracle` | 0.423 | 0.369 | -0.053 (-0.122 to +0.013) | 0.1222 | 0.3666 | no significant difference |
