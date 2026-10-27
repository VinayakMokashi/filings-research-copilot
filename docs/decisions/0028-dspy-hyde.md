# ADR-0028: Keep the hand-written HyDE prompt; DSPy found no better instruction

- **Status:** Accepted
- **Date:** 2026-10-28
- **Phase:** 7

## Context

Step 7.3 optimises one prompt with DSPy and adopts the result only on a significant gain on FinanceBench dev. The HyDE prompt was chosen: its passage is one of the four searches the doc agent fuses (ADR-0012), and its quality can be measured without reference answers, by where the evidence ranks when the passage is the search. Training and validation use the synthetic questions about training filings, so no FinanceBench question shapes the prompt.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **Keep the hand-written prompt** | Measured since Phase 3; every rewrite cached | Never searched for |
| MIPROv2 over the instruction (light mode) | A principled search against a metric, cheap on Cerebras | Found nothing better (below) |
| MIPROv2 with worked examples | Often where DSPy gains most | The examples would carry the pairs' questions, which come from FinanceBench's filings and are never committed, and a prompt that must ship couldn't hold them |

## Decision

The HyDE prompt stays as it is. `HydePrompt`, `--hyde-prompt`, `CachedLLM(also_read=...)` and `poe optimise-hyde` stay, so another prompt can be searched for and tested without new code; DSPy stays a development dependency, outside the service images.

## Evidence

[DSPy on the HyDE prompt](../eval/dspy-hyde.md): over nine trials and four instructions (the hand-written one and three proposals), no candidate beat the hand-written instruction on the 104 validation questions (0.498 reciprocal rank to ten, against 0.497 for the best proposal), and MIPROv2 returned it. Two of the three proposals misread the task as retrieving a passage rather than writing one.

## Consequences

- No change to retrieval, and no rewrite to call again: every cached HyDE passage still serves.
- A later search could use worked examples written for the purpose, rather than taken from the pairs, or optimise the multi-query rewrite, which matters more to the fused ranking (ADR-0012).
- Pinning `dspy[optuna]` in the development tools adds optuna, SQLAlchemy, Alembic, Mako and colorlog to the lock file; none reaches a service image.

## References

- Khattab et al., [DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714), 2023.
- Opsahl-Ong et al., [Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs](https://arxiv.org/abs/2406.11695), 2024 (MIPROv2).
- Gao et al., [Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2212.10496), 2022 (HyDE).
- [ADR-0012](0012-query-understanding-and-rewriting.md); the [DSPy guide](../concepts/dspy.md).
