# Domain embedder, pipeline, mrr@10

mrr@10 on 100 paired dev questions against the baseline `page_bge-small-dense-rw-multi-hyde-decompose-understood`; paired permutation tests, Holm-adjusted across 3 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-fp32-dense-rw-multi-hyde-decompose-understood` | 0.476 | 0.476 | +0.001 (-0.001 to +0.003) | 1.0000 | 1.0000 | no significant difference |
| `page_embedder-v1-dense-rw-multi-hyde-decompose-understood` | 0.476 | 0.514 | +0.038 (-0.019 to +0.094) | 0.1903 | 0.5708 | no significant difference |
| `page_embedder-v2-dense-rw-multi-hyde-decompose-understood` | 0.476 | 0.486 | +0.011 (-0.038 to +0.061) | 0.6836 | 1.0000 | no significant difference |
