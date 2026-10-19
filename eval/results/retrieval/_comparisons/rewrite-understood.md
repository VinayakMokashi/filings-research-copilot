# Query rewriting, resolved filings

recall@10 on 100 paired dev questions against the baseline `page_bge-small-dense-understood`; paired permutation tests, Holm-adjusted across 4 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `page_bge-small-dense-rw-multi-understood` | 0.570 | 0.682 | +0.112 (+0.035 to +0.192) | 0.0064 | 0.0128 | better |
| `page_bge-small-dense-rw-hyde-understood` | 0.570 | 0.682 | +0.112 (+0.045 to +0.180) | 0.0024 | 0.0072 | better |
| `page_bge-small-dense-rw-decompose-understood` | 0.570 | 0.662 | +0.092 (+0.015 to +0.172) | 0.0293 | 0.0293 | better |
| `page_bge-small-dense-rw-multi-hyde-decompose-understood` | 0.570 | 0.722 | +0.152 (+0.077 to +0.230) | 0.0005 | 0.0020 | better |
