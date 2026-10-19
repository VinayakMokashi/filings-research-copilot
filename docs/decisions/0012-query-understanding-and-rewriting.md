# ADR-0012: Resolve the filings, then search three rewrites of the question

- **Status:** Accepted
- **Date:** 2026-10-19
- **Phase:** 3

## Context

ADR-0011 chose dense search over page chunks, measured with each question searching its own filing. A real question doesn't come with its filing attached, and searching all 84 filings lost a fifth of the evidence. ADR-0011 also traced most of what went wrong to the questions themselves: FinanceBench's templates add instructions that aren't about the topic, and questions name metrics ("quick ratio", "capital expenditure") that filings never print. It promised to re-test hybrid search and reranking once questions were rewritten.

The constraint is cost: the free model tier allows about 200,000 tokens a day per model, and answering will need most of that.

## Options considered

| Question | Options |
|---|---|
| Finding the filings | Search everything; rules over company names, periods and forms; ask a model to extract them |
| Rewriting | None; multi-query (three queries); HyDE (a hypothetical passage); decomposition (the facts the answer needs); all three, fused |
| Ranking on top | Dense alone; hybrid with BM25; bge-reranker-base over the top 20, against the question or against a clean rewrite |

## Decision

1. **Query understanding by rules** (`copilot.retrieval.query`): company names, aliases and tickers, fiscal periods, quarters, dates and forms resolve to the filings to search; forward-looking questions also search the previous year; with no company, search everything.
2. **All three rewrites, requested in parallel** (`copilot.retrieval.rewrite.aexpand`), each searched with dense vectors inside the resolved filings, fused with the original question's ranking by reciprocal rank fusion (k = 60).
3. **Dense search stays alone**: no BM25 fusion and no cross-encoder, re-tested and rejected again.
4. **Every model call is cached** (`copilot.llm.cache`) and batch calls are paced (`copilot.llm.pacing`).

## Evidence

FinanceBench dev, 100 questions, dense search over page chunks ([query understanding](../concepts/query-understanding.md), [query rewriting](../concepts/query-rewriting.md)):

| Setup | recall@10 | MRR@10 |
|---|---|---|
| All 84 filings | 0.415 | 0.230 |
| Filings resolved from the question | 0.570 | 0.381 |
| + multi-query | 0.682 | 0.454 |
| + HyDE | 0.682 | 0.388 |
| + decomposition | 0.662 | 0.415 |
| **+ all three** | **0.722** | **0.476** |
| The question's own filing, no rewriting (Phase 2's ceiling) | 0.630 | 0.423 |

- Query understanding beats searching everything on both metrics (p = 0.0001). It finds a company in 98 questions and includes the question's own filing in all 98.
- Every rewrite beats none on recall@10 (Holm-adjusted p from 0.002 to 0.029); only all three together is also significantly better on MRR@10 (p = 0.018). All three against multi-query alone: +0.040 recall@10, not significant, for three times the tokens (about 630 a question).
- Re-tested on the rewrites (Holm-adjusted over three): hybrid search 0.697 recall@10 and 0.436 MRR, not significantly different; bge-reranker-base against the question 0.650 and 0.335, significantly worse on MRR (p = 0.002); bge-reranker-base against the first multi-query rewrite 0.692 and 0.436, not significantly different, and about 8 seconds a question on a laptop CPU. Rewriting the reranker's query recovered most of what the template text cost it, but not enough to beat dense search.
- Rules cost no model call. All three rewrites cost about 63,000 tokens per 100 questions, once; reruns come from the cache.

## Consequences

- With rewriting, retrieval across the resolved filings beats Phase 2's own-filing ceiling, so answering starts from better evidence than the baseline measured in ADR-0011.
- Each question costs three fast-model calls before search. Run in parallel, they add about one call's latency (about 1.4 seconds at p50 on Groq).
- The rules were written while reading dev questions. They may miss phrasings the test set uses; the milestone evaluation on the held-out split checks that.
- Reranking and BM25 stay out of the pipeline. Questions that differ in kind from FinanceBench's might change that, so the code paths remain.

## References

- Gao et al., [Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2212.10496) (HyDE), 2022.
- Rackauckas, [RAG-Fusion](https://arxiv.org/abs/2402.03367), 2024.
- ADR-0011 and the [retrieval baseline report](../eval/retrieval-baseline.md).
