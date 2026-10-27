# Decision records

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-choose-filings-research-copilot.md) | Build an analyst copilot over SEC filings | Accepted | 2026-10-15 |
| [0002](0002-documentation-system.md) | Keep all project documentation in the repo | Accepted | 2026-10-15 |
| [0003](0003-aws-demo-windows.md) | Run the AWS deployment in demo windows | Superseded by 0016 | 2026-10-15 |
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
| [0015](0015-reuse-text2sql-analyst.md) | Reuse text2sql-analyst as a pinned dependency, improved upstream first | Accepted | 2026-10-23 |
| [0016](0016-deploy-on-google-cloud.md) | Deploy on Google Cloud, with services that scale to zero | Accepted | 2026-10-23 |
| [0017](0017-routing.md) | Route with an LLM on the strong model, and keep a semantic router as its fallback | Accepted | 2026-10-24 |
| [0018](0018-graph-design.md) | Orchestrate the copilot as a LangGraph state graph | Accepted | 2026-10-24 |
| [0019](0019-validator-loop.md) | Check every cited sentence before an answer is shown, and revise what fails at most twice | Accepted | 2026-10-25 |
| [0020](0020-api-and-streaming.md) | Serve the copilot over HTTP with FastAPI, streaming the graph's events as server-sent events | Accepted | 2026-10-26 |
| [0021](0021-mcp-server.md) | Serve the copilot over MCP, with lookups in the server and questions through the API | Accepted | 2026-10-26 |
| [0022](0022-containers.md) | Build two images from one Dockerfile, and mount the data rather than build it in | Accepted | 2026-10-26 |
| [0023](0023-observability.md) | Trace each run in Langfuse from the graph's own events | Accepted | 2026-10-27 |
| [0024](0024-second-provider.md) | Finish Phase 5's evaluations on a second provider, with each model called as it was measured | Accepted | 2026-10-27 |
| [0025](0025-classifier-router.md) | Use a LoRA-tuned classifier as the LLM router's fallback, and keep the LLM router first | Accepted | 2026-10-27 |
| [0026](0026-copilot-v2.md) | Hand on what the data agent can't answer, route by the database's grain, and let a checked answer keep a labelled assessment | Accepted | 2026-10-27 |
| [0027](0027-domain-embedder.md) | Keep bge-small; the embedders fine-tuned on filings aren't adopted | Accepted | 2026-10-28 |

New records copy [0000-template.md](0000-template.md) and take the next number.
