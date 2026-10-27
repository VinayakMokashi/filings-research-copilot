# Domain embedder, pipeline, recall@10

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-rw-multi-hyde-decompose-understood`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-rw-multi-hyde-decompose-understood` | 0.722 | 0.722 | +0.000 (+0.000 to +0.000) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-rw-multi-hyde-decompose-understood` | 0.722 | 0.747 | +0.025 (-0.040 to +0.092) | 0.5127 | 1.0000 | no significant difference |
| `page_embedder-v2-dense-rw-multi-hyde-decompose-understood` | 0.722 | 0.742 | +0.020 (-0.047 to +0.087) | 0.6254 | 1.0000 | no significant difference |
