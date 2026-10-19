# Hybrid search and reranking on rewritten queries

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-rw-multi-hyde-decompose-understood`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-hybrid-rw-multi-hyde-decompose-understood` | 0.476 | 0.435 | -0.040 (-0.094 to +0.012) | 0.1355 | 0.2710 | no significant difference |
| `page_bge-small-dense-rerank-bge-base-rw-multi-hyde-decompose-understood` | 0.476 | 0.335 | -0.141 (-0.216 to -0.069) | 0.0006 | 0.0018 | worse |
| `page_bge-small-dense-rerank-bge-base-rq-rw-multi-hyde-decompose-understood` | 0.476 | 0.436 | -0.040 (-0.102 to +0.023) | 0.2203 | 0.2710 | no significant difference |
