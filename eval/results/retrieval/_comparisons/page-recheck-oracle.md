# Page chunks: search mode and reranking, oracle document

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-oracle` | 0.630 | 0.430 | -0.200 (-0.300 to -0.105) | 0.0002 | 0.0006 | worse |
| `page_bge-small-hybrid-oracle` | 0.630 | 0.585 | -0.045 (-0.115 to +0.020) | 0.2494 | 0.4988 | no significant difference |
| `page_bge-small-dense-rerank-bge-base-oracle` | 0.630 | 0.615 | -0.015 (-0.080 to +0.050) | 0.7670 | 0.7670 | no significant difference |
