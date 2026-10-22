# errors: doc-agent-v3-full--qwen3.8-27b-p2 (dev)

100 questions; outcomes by judge `qwen3.8-27b-p2`. Categories follow `copilot.eval.errors`.

| Category | domain-relevant | metrics-generated | novel-generated | All |
|---|---|---|---|---|
| correct | 20 | 29 | 16 | 65 |
| refused, evidence retrieved | 1 | 1 | 0 | 2 |
| refused, evidence not retrieved | 1 | 1 | 2 | 4 |
| calculation broke | 3 | 0 | 1 | 4 |
| evidence not retrieved | 3 | 0 | 5 | 8 |
| wrong with the evidence in context | 6 | 2 | 9 | 17 |

Retried: 16. Failed calculations: 11. Unfilled placeholders: 3.
Model latency p50 2.34 s, p95 5.52 s. Cost at list prices: $0.1107 in all, $0.001107 a question.
