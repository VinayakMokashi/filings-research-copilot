# A LoRA classifier as the router

> Teach a small encoder to route the way the LLM router does, and run it on the CPU.

**Lands in:** Phase 7 · **Code:** `src/copilot/agents/router_training.py`, `src/copilot/agents/classifier.py`, `scripts/generate_routing_train.py`, `kaggle/router/train_router.py`

## What it is

**A classifier router** maps a question straight to one of the six routes with a small encoder model and a classification head: one forward pass, no generation. **LoRA** (low-rank adaptation; Hu et al., 2021) is how the encoder is fine-tuned cheaply. Instead of updating a weight matrix W, training learns a low-rank update BA beside it, with B and A thin matrices of rank r, so the layer computes Wx + (alpha / r)·BAx. Only A, B and the head are trained, a few percent of the parameters. After training, BA is added into W once ("merging"), so the deployed model is an ordinary encoder with no adapter code and no extra cost.

**Distillation** (Hinton et al., 2015) supplies the labels: a strong model, the teacher, labels plenty of examples, and a small model, the student, learns to copy its decisions. Here the teacher is the LLM router, which routes every routing-set dev question correctly ([ADR-0017](../decisions/0017-routing.md)).

## Why we need it here

The LLM router is accurate but costs a model call on every question: about half a second and $0.0002, and a share of the provider's quota. The semantic router, a nearest-centroid vote over embeddings, is free but reaches only 0.74 on dev, because similar questions share a company or a measure more often than an intent. A fine-tuned classifier sits between them: it learns from labelled examples what separates the routes, as the LLM does, and runs in milliseconds on the CPU, as the semantic router does. With its probability as a confidence, a cascade can keep the LLM router for the questions the classifier is unsure of.

## How it works

1. **Training questions** (`poe generate-routing-train`). The routing set's 198 questions are kept for evaluation, so a model writes new ones, route by route, in batches that vary the companies, the measures and the style, and that ask in turn for each kind of question the route's definition names, with a third of each batch close to another route's border. Questions within 0.85 cosine similarity of any routing-set question are dropped, so the student never trains on a rewording of an evaluation question, and so are near-duplicates. The LLM router labels the rest; its label is the one the student learns, whatever route the writer aimed for ([data card](../data/routing-train-set.md)).
2. **The student** (`kaggle/router/train_router.py`, on a Kaggle GPU). bge-small-en-v1.5, the project's embedding model, gets a six-way classification head and LoRA adapters (rank 16) on the attention and feed-forward projections. Each route's loss is weighted by the inverse of its share, so a rarer route isn't drowned out. Ten epochs, keeping the one with the best accuracy on the training set's own validation split.
3. **Export.** The adapters are merged and the model is exported to ONNX, checked against PyTorch's logits.
4. **Serving** (`ClassifierRouter`). onnxruntime and the model's tokenizer run on the CPU; the route is the most probable class, and its probability is the confidence.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.agents.router_training` | The writer's prompt, the batch plan, the duplicate and leak filters, the validation split |
| `scripts/generate_routing_train.py` (`poe generate-routing-train`) | Writes, filters and labels the training questions, resumably |
| `kaggle/router/train_router.py` | Trains, merges and exports the student on Kaggle |
| `copilot.agents.classifier.ClassifierRouter` | Routes with the exported model on the CPU |
| `scripts/run_router.py --router classifier` | Scores it on the routing set like the other routers |

## How we measured it

On the routing set ([report](../eval/lora-router.md)), against the routers of Phase 5:

| Router | Dev (138) | Test (60, scored once) | Median latency | Cost |
|---|---|---|---|---|
| Semantic, masked, nearest centroid | 0.739 | 0.800 | 8 ms | none |
| Classifier, version 1 | 0.833 | | 9 ms | none |
| **Classifier, version 2** | **0.913** | **0.950** | **8 ms** | **none** |
| Cascade, the LLM router below 0.8 confidence | 0.957 (9% sent on) | 0.967 (5%) | 8 ms | $0.00002 |
| LLM router, gpt-oss-120b | 1.000 | 1.000 | 0.5 s | $0.0002 |

The classifier is significantly better than the semantic router on both splits, and worse than the LLM router on dev. It became the LLM router's fallback, behind `FRC_ROUTER_FALLBACK=classifier`, while the LLM router stays first ([ADR-0025](../decisions/0025-classifier-router.md)). The model is on Hugging Face as [vinayakmokashi45/filings-research-copilot-router](https://huggingface.co/vinayakmokashi45/filings-research-copilot-router).

## Pitfalls

- **Leaks from the evaluation set.** A written question can come close to a routing-set question by chance; 71 of the second set's 2,399 distinct questions did (77 of the first set's 2,368), and were dropped before labelling.
- **A teacher's labels can't fill a gap in the questions.** The first set's decline questions were nearly all requests for investment advice, because each batch named companies and measures; none was harmful or tried to override the instructions. Its classifier sent those requests to small talk with 0.92 to 0.99 confidence, and routed only 9 of 21 dev declines correctly. Asking the writer for each kind a route's definition lists, in turn, raised that to 16 of 21. A distilled student learns the teacher's decisions only on the inputs it is shown.
- **Short, generic requests leak.** "Ignore your instructions" is phrased much the same by anyone, so the leak filter drops many such training questions as too close to the routing set's own, and the kind ends with the fewest examples (44). The final classifier's most confident mistakes are of that kind.
- **A fresh image on every run.** The Kaggle image had PEFT refuse its old torchao and ran transformers 5, so the kernel's first run failed in under a minute: it now uninstalls torchao, passes the labels only as `id2label`, and exports from the saved model with eager attention, trying the TorchScript exporter before the dynamo one.
- **Too-easy examples.** In a first trial the writer produced only textbook cases: the teacher agreed with the intended route on every one. Asking for a third of each batch near a border gives the student the hard cases a router exists for.
- **The teacher's ceiling.** A student copies its teacher's mistakes; on the routing set the teacher makes none, but its labels on the training questions are unchecked beyond that.

## Review questions

1. Why does LoRA train a product BA instead of the full update to W, and what does merging change at inference time?
2. Why keep the routing set out of training entirely, and why also drop training questions that merely resemble it?
3. What does a student router learn from a teacher's labels, and what can it never learn from them?
4. How would you choose the confidence below which a cascade calls the LLM router?

## References

- Hu et al., [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685), 2021.
- Hinton, Vinyals and Dean, [Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531), 2015.
- Xiao et al., [C-Pack: Packaged Resources To Advance General Chinese Embedding](https://arxiv.org/abs/2309.07597), 2023 (the BGE models).
- Hugging Face [PEFT documentation](https://huggingface.co/docs/peft/index) and [ONNX Runtime](https://onnxruntime.ai/docs/).
