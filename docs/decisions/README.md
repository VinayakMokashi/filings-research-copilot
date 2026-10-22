# Decision records

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-choose-filings-research-copilot.md) | Build an analyst copilot over SEC filings | Accepted | 2026-10-15 |
| [0002](0002-documentation-system.md) | Keep all project documentation in the repo | Accepted | 2026-10-15 |
| [0003](0003-aws-demo-windows.md) | Run the AWS deployment in demo windows | Accepted | 2026-10-15 |
| [0004](0004-tooling-and-workflow.md) | Tooling, repository layout and Git workflow | Accepted | 2026-10-15 |
| [0005](0005-llm-gateway.md) | One LLM gateway built on LiteLLM's router | Accepted | 2026-10-15 |
| [0006](0006-evaluation-splits.md) | Split FinanceBench by company into dev and held-out test | Accepted | 2026-10-17 |
| [0007](0007-evaluation-statistics.md) | Report bootstrap intervals and decide with paired permutation tests | Accepted | 2026-10-17 |
| [0008](0008-xbrl-normalisation.md) | Normalise XBRL company facts into annual values as first reported | Accepted | 2026-10-17 |
| [0009](0009-pdf-parsing.md) | Parse filings with pdfium, page by page | Accepted | 2026-10-17 |
| [0010](0010-vector-store-and-embeddings.md) | Index chunks in Qdrant with bge-small and BM25 vectors | Accepted | 2026-10-17 |
| [0011](0011-retrieval-baseline.md) | Start the doc agent from dense search over page chunks | Accepted | 2026-10-18 |
| [0012](0012-query-understanding-and-rewriting.md) | Resolve the filings, then search three rewrites of the question | Accepted | 2026-10-19 |
| [0013](0013-answer-format.md) | Answer from numbered sources in JSON, with a calculator and one retry aimed at what is missing | Accepted | 2026-10-19 |
| [0014](0014-answer-judge.md) | Grade answers with a rubric-bound model judge, checked against reference labels | Accepted | 2026-10-23 |

New records copy [0000-template.md](0000-template.md) and take the next number.
