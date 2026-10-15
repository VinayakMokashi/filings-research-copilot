# ADR-0001: Build an analyst copilot over SEC filings

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** Planning

## Context

Answering a question about a public company means reconciling two sources: the narrative in its 10-K and 10-Q filings, and the figures it reports as XBRL facts. General-purpose LLM tools handle this poorly. On FinanceBench, GPT-4-Turbo with a retrieval system answered 81% of the sampled questions incorrectly or refused to answer them (Islam et al., 2023). The goal is a deployable copilot that answers from both sources, cites every claim to a page or a query, declines when the evidence is missing, and reports its accuracy on that benchmark.

Constraints: development on a laptop without a CUDA GPU, a free-tier-first budget, and an earlier tested project (text2sql-analyst) that can be reused.

## Options considered

| Option | Summary | Strengths | Weaknesses |
|---|---|---|---|
| **A. Filings Research Copilot** | Agentic RAG over SEC filings, Text-to-SQL over XBRL facts, fine-tuned retrieval and routing; AWS on demand | A clear analyst need; free public data (SEC EDGAR); an external benchmark (FinanceBench); reuses text2sql-analyst for the numbers | Largest scope |
| B. Code review agent | GitHub App: code retrieval, sandboxed tool-using agents, MCP; event-driven serverless | A current developer-tools need; public repositories to test on | Crowded market; sandboxing untrusted code is hard; no reuse of text2sql-analyst |
| C. Adaptive study tutor | Generated practice questions, knowledge tracing, adaptive scheduling; serverless | Personalised practice is a clear user benefit | Measuring learning gains needs real learners over weeks; no public benchmark to compare against |

## Decision

Build option A, the Filings Research Copilot.

## Consequences

- The scope is large, so each phase delivers standalone value and stretch items are marked.
- text2sql-analyst becomes the data agent. Improvements made here (value linking, a Postgres executor) can go back upstream.
- FinanceBench is used for evaluation only; its licence is checked in Phase 1.
- The bandit idea from option C is reused for cost-aware model routing in Phase 7: choosing between the strong and fast models per query, rewarded by answer quality minus cost, to stay within free-tier rate limits.

## References

- Islam et al., *FinanceBench: A New Benchmark for Financial Question Answering* (2023): https://arxiv.org/abs/2311.11944
- SEC EDGAR APIs: https://www.sec.gov/edgar/sec-api-documentation
