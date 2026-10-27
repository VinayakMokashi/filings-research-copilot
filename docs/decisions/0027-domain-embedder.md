# ADR-0027: Keep bge-small; the embedders fine-tuned on filings aren't adopted

- **Status:** Accepted
- **Date:** 2026-10-28
- **Phase:** 7

## Context

Retrieval bounds what the doc agent can answer: with query understanding and three rewrites, an evidence page reaches the top ten for 0.722 of FinanceBench's dev questions ([ADR-0012](0012-query-understanding-and-rewriting.md)). The embedding model, bge-small-en-v1.5, was trained on general web text. Step 7.1 fine-tunes it on 1,006 synthetic questions about training filings, with hard negatives mined from the filings, and asks whether the doc agent's search improves. The rule for every Phase 7 experiment is to adopt only on a significant gain on fixed evaluation sets.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **Keep bge-small (FastEmbed's quantized export)** | The measured baseline; nothing to train, host or ship | No gain from the domain |
| Version 1: all negatives from the question's own filing | MRR@10 on held-out training filings 0.41 → 0.71; +0.025 recall@10 in the doc agent's pipeline (not significant) | Significantly worse across all filings (−0.135 recall@10, −0.096 MRR@10); half its top pages come from other companies |
| Version 2: one negative from another company, validated across filings | Recovers part of the loss across filings (−0.080 and −0.068, not significant after adjustment) | +0.020 recall@10 and +0.011 MRR@10 in the pipeline, not significant; still worse across filings |

## Decision

The doc agent keeps bge-small. Neither fine-tuned embedder is adopted or published. The path a later model would take stays in the code: `OnnxDense` for an exported encoder, collections built from vectors a GPU computed (`poe index-corpus --vectors`), a collection's index card choosing its query model, `FRC_COLLECTION` choosing the doc agent's collection, and `poe kaggle-embedder` training from a private Kaggle dataset.

## Evidence

[A domain embedder, fine-tuned on filings](../eval/domain-embedder.md), FinanceBench dev, 100 questions, Holm-adjusted over three candidates:

- **The doc agent's pipeline:** production 0.722 recall@10 and 0.476 MRR@10; version 1 0.747 and 0.514 (p = 1.00 and 0.57); version 2 0.742 and 0.486 (p = 1.00 and 1.00).
- **All 84 filings:** production 0.415 and 0.230; version 1 0.280 and 0.134 (p = 0.028 and 0.007, worse); version 2 0.335 and 0.162 (p = 0.22 and 0.073).
- **The question's own filing:** no significant difference; MRR@10 0.05 lower for both versions.
- **The control:** the base model exported in full precision the same way matches production to within 0.001 on every metric, so the comparison measures the fine-tuning, not the export.

## Consequences

- No new model to host, and no index to rebuild for Phase 8: the deployment's Qdrant collection keeps bge-small's vectors.
- The training data's licence question doesn't arise for a published model: pairs from FinanceBench's filings (CC BY-NC 4.0) would have made any published embedder non-commercial.
- The infrastructure is tested and documented, so a later attempt (questions in the style of real users, paired with page chunks; validation across filings as well as within them; judged on the pipeline) costs a kernel run and an evaluation, not new code.
- Version 1's lesson carries to any contrastive training here: negatives from one filing teach topics, not companies, and a validation that ranks within one filing can't see a model mixing up companies.

## References

- Henderson et al., [Efficient Natural Language Response Suggestion for Smart Reply](https://arxiv.org/abs/1705.00652), 2017.
- Karpukhin et al., [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906), 2020.
- Moreira et al., [NV-Retriever: Improving text embedding models with effective hard-negative mining](https://arxiv.org/abs/2407.15831), 2024.
- [ADR-0011](0011-retrieval-baseline.md) and [ADR-0012](0012-query-understanding-and-rewriting.md); the [contrastive fine-tuning guide](../concepts/contrastive-finetuning.md).
