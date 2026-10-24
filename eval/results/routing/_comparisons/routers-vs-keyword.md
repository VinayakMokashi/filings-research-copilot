# Routers against the keyword rules (routing dev)

accuracy on 138 paired dev questions against the baseline `keyword`; paired permutation tests, Holm-adjusted across 4 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `semantic-masked-centroid` | 0.623 | 0.739 | +0.116 (+0.007 to +0.225) | 0.0511 | 0.0511 | no significant difference |
| `llm-gpt-oss-20b` | 0.623 | 0.964 | +0.341 (+0.261 to +0.427) | 0.0001 | 0.0004 | better |
| `llm-gpt-oss-120b` | 0.623 | 1.000 | +0.377 (+0.297 to +0.457) | 0.0001 | 0.0004 | better |
| `llm-qwen3.8-27b` | 0.623 | 1.000 | +0.377 (+0.297 to +0.457) | 0.0001 | 0.0004 | better |
