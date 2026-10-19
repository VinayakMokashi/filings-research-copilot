# Hybrid search and reranking on rewritten queries

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-rw-multi-hyde-decompose-understood`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-hybrid-rw-multi-hyde-decompose-understood` | 0.722 | 0.697 | -0.025 (-0.070 to +0.020) | 0.4110 | 0.6695 | no significant difference |
| `page_bge-small-dense-rerank-bge-base-rw-multi-hyde-decompose-understood` | 0.722 | 0.650 | -0.072 (-0.140 to -0.007) | 0.0479 | 0.1437 | no significant difference |
| `page_bge-small-dense-rerank-bge-base-rq-rw-multi-hyde-decompose-understood` | 0.722 | 0.692 | -0.030 (-0.080 to +0.020) | 0.3348 | 0.6695 | no significant difference |
