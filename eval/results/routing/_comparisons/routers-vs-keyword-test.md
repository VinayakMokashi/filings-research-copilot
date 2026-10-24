# Routers against the keyword rules, test split

accuracy on 60 paired test questions against the baseline `keyword`; paired permutation tests, Holm-adjusted across 2 comparisons, alpha 0.05.

| Candidate | Baseline | Candidate | Difference (95% interval) | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| `semantic-masked-centroid` | 0.650 | 0.800 | +0.150 (+0.000 to +0.300) | 0.0799 | 0.0799 | no significant difference |
| `llm-gpt-oss-120b` | 0.650 | 1.000 | +0.350 (+0.233 to +0.483) | 0.0001 | 0.0002 | better |
