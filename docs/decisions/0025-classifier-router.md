# ADR-0025: Use a LoRA-tuned classifier as the LLM router's fallback, and keep the LLM router first

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** 7

## Context

Every question passes through the router. The LLM router on gpt-oss-120b routes all 198 routing-set questions correctly, for about half a second, $0.0002 and some provider quota a question ([ADR-0017](0017-routing.md)). When its call fails, the semantic router decides instead: free and fast on the CPU, but right on only 0.74 of the dev questions and 0.80 of the test questions, because generic embeddings measure what a question is about rather than what it asks.

Step 7.2 tests whether a small encoder, fine-tuned on questions the LLM router labelled, can take either role: the router itself, the first stage of a cascade, or the fallback.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep the semantic router as the fallback | Nothing to ship | 0.74 on dev, 0.80 on test |
| **The classifier as the fallback, the LLM router first** | 0.17 better than the semantic router on dev and 0.15 on test, at the same cost and speed | A 134 MB model to ship; it learned prompt r1's routing |
| A cascade: the classifier first, the LLM router below 0.8 confidence | 9% of the LLM calls on dev (5% on test); 0.957 and 0.967 | 0.043 less accurate than the LLM router on dev (p = 0.03), to save about 4% of a question's cost |
| The classifier as the router | No model call at all, 8 ms | 0.087 less accurate on dev (p = 0.001); confidently routes requests to reveal its instructions to small talk |

## Decision

The classifier (bge-small-en-v1.5 with LoRA, merged, served with onnxruntime) becomes the LLM router's fallback when `FRC_ROUTER_FALLBACK=classifier` and its model is in `FRC_ROUTER_MODEL_DIR`. The default stays the semantic router until the model ships with the deployment (Phase 8, from the Hugging Face repository). The LLM router stays first, and decides every question it can.

## Evidence

[A LoRA classifier as the router](../eval/lora-router.md):

- **Classifier version 2:** 0.913 (0.862 to 0.957) on dev and 0.950 (0.883 to 1.000) on the test split, scored once; 8 ms at the median on a laptop CPU; no cost.
- **Against the semantic router:** +0.174 on dev (p = 0.0001) and +0.150 on test (p = 0.035).
- **Against the LLM router:** −0.087 on dev (p = 0.001), −0.050 on test (p = 0.25). A cascade at 0.8: −0.043 on dev (p = 0.03), −0.033 on test (p = 0.50), with 9% and 5% of questions sent on.
- **Version 1 of the training set** left four of the decline route's seven kinds out, and its classifier routed 9 of 21 dev declines correctly (0.833 overall). Asking the writer for every kind a route's definition names raised that to 16 of 21.

## Consequences

- When the LLM call fails, a question is now far more likely to reach the right agent, with no model call and no network.
- The deployment has one more artefact: the model is published at [vinayakmokashi45/filings-research-copilot-router](https://huggingface.co/vinayakmokashi45/filings-research-copilot-router), and Phase 8 downloads it at startup or bakes it into the image.
- The classifier copies prompt r1. The copilot's version 2 routes with prompt r2 ([ADR-0026](0026-copilot-v2.md)), whose rules on the database's grain the classifier never saw. Before it is used for more than a fallback, it should be trained again on r2's labels; the generator, the kernel and the evaluation run again as they are.
- The classifier's most confident mistakes are requests to reveal or override its instructions, which it routes to small talk. As a fallback only, that matters only when the LLM router is down; the copilot's prompt-injection defences apply either way.

## References

- Hu et al., [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685), 2021.
- Hinton, Vinyals and Dean, [Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531), 2015.
- [ADR-0017](0017-routing.md), routing; the [LoRA classifier guide](../concepts/lora-classifier.md).
