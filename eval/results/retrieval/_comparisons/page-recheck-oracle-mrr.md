# Page chunks: search mode and reranking, oracle document (MRR@10)

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-oracle`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-bm25-oracle` | 0.423 | 0.243 | -0.180 (-0.267 to -0.094) | 0.0002 | 0.0006 | worse |
| `page_bge-small-hybrid-oracle` | 0.423 | 0.334 | -0.089 (-0.156 to -0.026) | 0.0092 | 0.0184 | worse |
| `page_bge-small-dense-rerank-bge-base-oracle` | 0.423 | 0.335 | -0.088 (-0.154 to -0.022) | 0.0100 | 0.0184 | worse |
