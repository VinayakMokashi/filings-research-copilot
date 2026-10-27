# Contrastive fine-tuning of the embedder

> Teach the embedding model what a question about a filing looks like, from questions written about the filings themselves.

**Lands in:** Phase 7 · **Code:** `src/copilot/training/embedder.py`, `kaggle/embedder/train_embedder.py`, `scripts/kaggle_embedder.py`, `src/copilot/ingest/embed.py` (`OnnxDense`), `scripts/index_corpus.py`

## What it is

The doc agent finds evidence with a **bi-encoder**: one model turns the question into a vector and, separately, every passage of a filing into a vector, and search ranks the passages by the cosine of the angle between the question's vector and theirs. The model is bge-small-en-v1.5, trained by its authors on a broad mix of web questions and passages. **Fine-tuning** it on this project's own domain means showing it questions paired with the filing passages that answer them, and adjusting its weights so each question lands nearer its passage than any other.

**Contrastive** training does that with a loss over a whole batch at once. For a batch of B questions q₁…q_B, each with its passage p₁…p_B, the model scores every question against every passage, multiplies the cosines by a scale s, and asks for the right passage to win a softmax over the row:

loss_i = −log( exp(s·cos(q_i, p_i)) / Σ_j exp(s·cos(q_i, p_j)) )

This is the InfoNCE loss; sentence-transformers calls it **MultipleNegativesRankingLoss** (MNRL). Every other question's passage serves as a negative for free (**in-batch negatives**), so a batch of 32 gives each question 31 negatives without any labelling. The scale s (20 here, a temperature of 0.05) sets how sharply the softmax separates a winner from the rest.

**Hard negatives** are passages that look relevant and aren't. Random passages from other companies are easy: the model already knows a question about 3M isn't answered by a page of Pfizer's. The useful lesson is finer: another page of the same 3M 10-K, with the same company, year and vocabulary, that states a different fact. Mining finds them with the base model itself, as the passages of the question's own filing that it ranks highest.

The hardest negatives carry a risk: a "negative" may answer the question too (filings repeat their figures in the statements, the MD&A and the notes), and training would then push the model away from a correct answer. **Positive-aware mining** (NV-Retriever; Moreira et al., 2024) leaves out any candidate that scores at least 95% of the positive's score, as likely to be a false negative.

## Why we need it here

Retrieval bounds everything the doc agent can answer: an evidence page that never reaches the context can't be cited. After query understanding and three rewrites, recall@10 on FinanceBench dev is 0.722 ([ADR-0012](../decisions/0012-query-understanding-and-rewriting.md)), and much lower for the analyst-style questions (domain-relevant 0.61, novel-generated 0.64) than for the templated metrics questions (0.92). Filings have a vocabulary of their own (Item 7, segment names, non-GAAP measures, the phrasing of risk factors) that a general web model has seen little of.

Fine-tuning a 33-million-parameter encoder takes minutes on a free GPU, and the result runs on the CPU exactly as bge-small does. Step 2.6 wrote the training data ahead of time: 1,006 questions, each about one 480-token chunk of a training filing ([data card](../data/synthetic-pairs.md)).

## How it works

1. **The data** (`poe kaggle-embedder` → `copilot.training.embedder`). The pairs come only from training filings: no filing of a test company, and no filing a dev question uses ([ADR-0006](../decisions/0006-evaluation-splits.md)). Every pair of a seeded tenth of those filings (20 filings, 104 pairs) is held out for validation, whole filings at a time, so validation asks about filings the model never trained on, as the dev questions do. The filing text can't be committed (FinanceBench's filings are CC BY-NC 4.0), so the data travel to Kaggle as a private dataset rather than through GitHub, and only counts and checksums are committed ([manifest](../../data/reference/embedder_data_manifest.json)).
2. **Mining** (the kernel's first step). The base model embeds the training filings' 50,310 chunks and the questions. For each pair, the chunks of its own filing are ranked by the question; the positive is skipped, and so are its two neighbours, which share 64 tokens with it, and any chunk scoring at least 95% of the positive's score. The next three are its hard negatives.
3. **Training.** The whole model is trained (no adapters: 33 million parameters fit easily), with MNRL over batches of 32 questions, each with its positive and its three hard negatives, so every question meets 127 negatives. A passage that is the question's own positive, or a neighbour of it, never counts as a negative, even when it arrives as another question's negative. Three learning rates (1e-5, 2e-5, 5e-5) run for up to three epochs each, with a 10% warmup, mixed precision and gradient checkpointing; the epoch with the best MRR@10 on validation is kept, where a question's chunk is ranked among all the chunks of its filing. Queries carry bge's instruction ("Represent this sentence for searching relevant passages: "), as they do at search time.
4. **Export.** The trained model is exported to ONNX with the last hidden state as its output; CLS pooling and unit length happen in `OnnxDense`, as they do for bge. The base model is exported the same way, as a control.
5. **Vectors for the evaluation.** The kernel embeds the 23,585 page chunks of the 84 filings behind FinanceBench's questions with both models, in fp32. `poe index-corpus --vectors` stores them in Qdrant, after embedding a sample again on the CPU to check they agree, and the index card records the model, so searches embed their queries with it.
6. **The comparison.** The same retrieval pipeline, with the same cached rewrites, runs over three collections: the production index (FastEmbed's quantized bge-small), the base model in fp32 (the control) and the fine-tuned model. Comparing the fine-tuned model with the control isolates what training did; comparing the control with production isolates the export.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.training.embedder` | The validation split by filing, the dataset's records, its fixed bytes and its manifest |
| `copilot.training.kaggle` | The Kaggle CLI: private datasets, GPU kernels, waiting and downloading |
| `kaggle/embedder/train_embedder.py` | Mining, training, the learning-rate grid, the ONNX exports and the corpus's vectors |
| `scripts/kaggle_embedder.py` (`poe kaggle-embedder`) | Writes the data, uploads it when it changes, runs the kernel, downloads the output |
| `copilot.ingest.embed.OnnxDense` | Serves an exported encoder on the CPU |
| `scripts/index_corpus.py --model-dir --vectors` | Builds a collection from vectors computed on the GPU |
| `FRC_COLLECTION` | Chooses the doc agent's collection; its card chooses the query model |

## How we measured it

On held-out training filings, the training worked: MRR@10 within the question's filing rose from 0.41 to 0.71 (version 1), and version 2 also rose across filings, from 0.25 to 0.43. On FinanceBench's dev questions it barely transferred ([report](../eval/domain-embedder.md)):

| Setting (recall@10 / MRR@10) | bge-small | Version 1 | Version 2 |
|---|---|---|---|
| The question's own filing, no rewriting | 0.630 / 0.423 | 0.660 / 0.373 | 0.645 / 0.369 |
| All 84 filings, no rewriting | 0.415 / 0.230 | **0.280 / 0.134** | 0.335 / 0.162 |
| The doc agent's pipeline | 0.722 / 0.476 | 0.747 / 0.514 | 0.742 / 0.486 |

No difference in the doc agent's pipeline is significant (Holm-adjusted paired tests), and version 1 is significantly worse across all filings. bge-small stays ([ADR-0027](../decisions/0027-domain-embedder.md)); the base model exported in full precision matches production to within 0.001, so the comparison measures the fine-tuning alone.

## Pitfalls we hit

- **A validation that can't see the failure.** Version 1's validation ranked a question's chunk among its own filing's chunks, as the doc agent searches resolved filings, and it rose from 0.41 to 0.71. Searching every filing, the same model took half its top pages from other companies (production: under a quarter). All its negatives came from the question's own filing, where the company name never separates one chunk from another, so the model learned topics and forgot companies. Version 2 took one negative from another company and validated across filings too; it recovered part of the loss.
- **Synthetic questions flatter.** A question written from a chunk names the company and period and echoes the chunk's words. Gains on such questions (0.2 to 0.3 MRR@10) say little about questions people write.
- **Margins on a compressed scale.** bge-small's cosines sit in a narrow band, so skipping candidates within 95% of the positive's score skipped about 32 a question in its own filing: the hard negatives were the 30th to 40th best chunks, not the hardest.
- **The data couldn't go through GitHub.** The pairs and chunks are FinanceBench filing text (CC BY-NC 4.0), so the kernel reads a private Kaggle dataset; a dataset just created, or a kernel just pushed, answers 403 to a status request for a minute or so, and the wait now treats that as "not ready yet".
- **A small evaluation.** A paired difference on 100 questions has a 95% interval about 13 points wide, so a real gain of two or three points can't be told from noise; a decision needs either a larger effect or more questions.

## Review questions

1. Why do in-batch negatives come for free, and what would a larger batch change?
2. What makes a hard negative hard, and why can the hardest ones teach the wrong lesson?
3. Why compare the fine-tuned model with the base model exported the same way, and not only with the production index?
4. The training questions were written by a model reading the passages they pair with. What does that do to what the embedder learns, and what in the evaluation guards against it?

## References

- van den Oord, Li and Vinyals, [Representation Learning with Contrastive Predictive Coding](https://arxiv.org/abs/1807.03748), 2018 (InfoNCE).
- Henderson et al., [Efficient Natural Language Response Suggestion for Smart Reply](https://arxiv.org/abs/1705.00652), 2017 (the multiple-negatives ranking loss).
- Karpukhin et al., [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906), 2020 (in-batch and hard negatives).
- Moreira et al., [NV-Retriever: Improving text embedding models with effective hard-negative mining](https://arxiv.org/abs/2407.15831), 2024 (positive-aware mining).
- Wang et al., [GPL: Generative Pseudo Labeling for Unsupervised Domain Adaptation of Dense Retrieval](https://arxiv.org/abs/2112.07577), 2022 (generated questions for domain adaptation).
- Xiao et al., [C-Pack: Packaged Resources To Advance General Chinese Embedding](https://arxiv.org/abs/2309.07597), 2023 (the BGE models).
- [sentence-transformers: MultipleNegativesRankingLoss](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss).
