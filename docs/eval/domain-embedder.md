# A domain embedder, fine-tuned on filings

Phase 7, step 7.1. Training and validation on synthetic pairs from training filings only; evaluation on FinanceBench dev, 100 questions, with the doc agent's own retrieval.

## Question

The doc agent's search finds an evidence page in its top ten for 0.722 of FinanceBench's dev questions, after query understanding and three rewrites ([ADR-0012](../decisions/0012-query-understanding-and-rewriting.md)), and for fewer of the analyst questions (0.61 of domain-relevant, 0.64 of novel-generated) than of the templated metrics questions (0.92). The embedding model is bge-small-en-v1.5, trained on general web text. Does fine-tuning it on questions about filings, with hard negatives from the filings themselves, rank evidence pages higher?

## Setup

- **Training data** ([data card](../data/synthetic-pairs.md)): the 1,006 synthetic questions of step 2.6, each written by a model about one 480-token chunk of a training filing (no filing of a test company, none a dev question uses). Every pair of a seeded tenth of those filings (20 filings, 104 pairs) is held out for validation; 902 pairs train. The filing text can't be committed (CC BY-NC 4.0), so the data reach Kaggle as a private dataset; the [manifest](../../data/reference/embedder_data_manifest.json) records counts and checksums, and the kernel recomputes them from what it reads.
- **Training** (`kaggle/embedder/train_embedder.py`, a Kaggle T4): the whole model (33.4 million parameters), MultipleNegativesRankingLoss with scale 20, batches of 32 questions, each with its chunk and three hard negatives, so 127 negatives a question; a passage that is the question's own chunk or a neighbour of it never counts as a negative. Hard negatives are mined with the base model and leave out the chunk's neighbours (64 tokens of overlap) and anything scoring at least 95% of the chunk's own score. Three learning rates (1e-5, 2e-5, 5e-5), up to three epochs each, 10% warmup, mixed precision. Queries carry bge's instruction, as at search time.
- **Two versions.** Version 1 mined all three negatives in the question's own filing and kept the epoch with the best MRR@10 within the filing. Version 2, written after version 1's dev results, mines two in the filing and one in other companies' filings, and keeps the epoch with the best mean of MRR@10 within the filing and across filings (the held-out filings' chunks and 10,000 from other training filings).
- **Export and vectors.** Both versions and, as a control, the base model are exported to ONNX the same way (onnxruntime matches PyTorch to within 3.1e-7). The kernel embeds the 23,585 page chunks of the 84 filings behind FinanceBench's questions in fp32; `poe index-corpus --vectors` stores them, after embedding 16 of them again on the laptop CPU (agreement within 3.9e-7). Queries are embedded on the CPU with the same ONNX model.
- **Evaluation:** the retrieval runs of ADR-0011 and ADR-0012, with the 300 rewrites replayed from the cache (no model calls; a replay of the production run reproduced all 100 rankings). Three settings: the question's own filing without rewriting, all 84 filings without rewriting, and the doc agent's pipeline (filings resolved from the question, three rewrites fused with the question by reciprocal rank fusion). Four collections: production (FastEmbed's quantized bge-small), the base model in fp32, version 1 and version 2.
- **Measures:** recall@10 and MRR@10 with 95% bootstrap intervals; paired permutation tests against production, Holm-adjusted over the three candidates in each setting and metric ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

### Validation, on held-out training filings

| Run | Within the filing, MRR@10 | Across filings, MRR@10 | Chosen |
|---|---|---|---|
| Version 1, base model | 0.410 | | |
| **Version 1, trained** | **0.714** (recall@10 0.962) | | 5e-5, epoch 2 |
| Version 2, base model | 0.376 | 0.254 | |
| **Version 2, trained** | **0.620** (recall@10 0.942) | **0.432** (recall@10 0.817) | 5e-5, epoch 3 |

Every learning rate improved on the base model at every epoch; the largest, 5e-5, did best in both versions. (The two versions' base numbers differ a little because their validation passes embed different chunks in half precision; within each version, before and after are measured alike.) On questions like the ones it trained on, the model learned a great deal.

### FinanceBench dev

| Setting | Metric | bge-small (production) | bge-small, fp32 | Version 1 | Version 2 |
|---|---|---|---|---|---|
| The question's own filing, no rewriting | recall@10 | 0.630 | 0.630 | 0.660 | 0.645 |
| | MRR@10 | 0.423 | 0.423 | 0.373 | 0.369 |
| All 84 filings, no rewriting | recall@10 | 0.415 | 0.415 | **0.280** | 0.335 |
| | MRR@10 | 0.230 | 0.231 | **0.134** | 0.162 |
| **The doc agent's pipeline** | **recall@10** | **0.722** | 0.722 | 0.747 | 0.742 |
| | **MRR@10** | **0.476** | 0.476 | 0.514 | 0.486 |

Paired differences against production, Holm-adjusted ([comparisons](../../eval/results/retrieval/_comparisons/)):

| Setting | Metric | Version 1 | Version 2 |
|---|---|---|---|
| The doc agent's pipeline | recall@10 | +0.025 (−0.040 to +0.092), p = 1.00 | +0.020 (−0.047 to +0.087), p = 1.00 |
| | MRR@10 | +0.038 (−0.019 to +0.094), p = 0.57 | +0.011 (−0.038 to +0.061), p = 1.00 |
| All 84 filings | recall@10 | **−0.135 (−0.235 to −0.040), p = 0.028** | −0.080 (−0.175 to +0.010), p = 0.22 |
| | MRR@10 | **−0.096 (−0.160 to −0.036), p = 0.007** | −0.068 (−0.131 to −0.006), p = 0.073 |
| The question's own filing | recall@10 | +0.030, p = 1.00 | +0.015, p = 1.00 |
| | MRR@10 | −0.049, p = 0.37 | −0.053, p = 0.37 |

**Neither version is significantly better anywhere, and version 1 is significantly worse when it searches every filing.** In the doc agent's pipeline, version 1 finds an evidence page in the top ten for 8 questions production misses and loses 4; version 2 wins 8 and loses 5. The wins are analyst questions (domain-relevant and novel-generated), which is where the gain was hoped for, but a difference of two or three points is well inside what 100 questions can't tell from noise.

### What went wrong across filings

Searching every filing, a question about one company should mostly find that company's pages. Of the top ten pages:

| Collection | The question's own filing | The company's other filings | Other companies |
|---|---|---|---|
| bge-small (production) | 0.343 | 0.425 | 0.232 |
| Version 1 | 0.237 | 0.252 | **0.511** |
| Version 2 | 0.284 | 0.287 | 0.429 |

Version 1 lost the company signal: half its top pages came from other companies. Its negatives were all in the question's own filing, where the company never tells one chunk from another, and its validation ranked within the filing, so it couldn't see the loss. Version 2's negative from another company and its validation across filings recovered part of it, not all. Inside the filings the doc agent's rules resolve (98 of 100 questions), the share of other companies stays at 0.018 for every model, which is why the pipeline barely notices.

### A side finding

FastEmbed's quantized bge-small and a full-precision export put the same pages in the top ten for 97 to 100 of the 100 questions, in every setting, and their metrics are within 0.001. The quantization the index uses costs nothing measurable.

## Why the gain didn't transfer

These are readings of the evidence, not measurements:

- **Synthetic questions are easier than real ones.** Each training question was written from the chunk it pairs with, names the company and period, and shares the chunk's vocabulary even after the copy filter. Validation asks the same kind of question, and gained 0.2 to 0.3 MRR@10; FinanceBench's human questions, with their templated instructions and metrics that filings never print, gained little.
- **The pipeline already does much of the work.** Rules resolve the filing for 98 questions, and three rewrites restate each question in the filing's own terms; what a domain embedder adds on top is small, and 100 questions can't measure a small gain (the 95% interval of a paired difference spans about 13 points).
- **Different units.** Training pairs questions with 480-token chunks that may cross pages; the index holds page chunks.

## Decision

**Keep bge-small; adopt neither fine-tuned model, and publish neither** ([ADR-0027](../decisions/0027-domain-embedder.md)). Neither is significantly better in the doc agent's pipeline, and both rank worse across filings, where a question that names no company is searched.

What stays is the path a better model would take: `OnnxDense` serves an exported encoder on the CPU, `poe index-corpus --model-dir --vectors` builds a collection from vectors a GPU computed, a collection's index card chooses its query model, `FRC_COLLECTION` chooses the doc agent's collection, and `poe kaggle-embedder` trains from a private dataset. A next attempt would pair human-style questions with page chunks, validate across filings as well as within them, and judge on the pipeline itself.

**Limits:** 100 dev questions; version 2 was designed after reading version 1's dev results, so its dev numbers aren't a fresh test either; the training questions come from models and no person read them; one seed per configuration.

## Logs

- Runs: `eval/results/retrieval/page_{bge-small-fp32,embedder-v1,embedder-v2}-dense-{oracle,corpus,rw-multi-hyde-decompose-understood}/dev/`, beside production's `page_bge-small-dense-*`; the comparisons in [`_comparisons/domain-embedder-*`](../../eval/results/retrieval/_comparisons/).
- Training: the kernels' `metrics.json` and logs, the models and the page vectors in `data/models/embedder-v1` and `embedder-v2` (git-ignored); Kaggle kernel `frc-embedder` (versions 1 and 2) and the private dataset `frc-embedder-data` (versions 1 and 2), 24 and 32 minutes on a T4.
- Reproduce ([runbook](../runbooks/training-models.md)):

  ```bash
  uv run poe kaggle-embedder --user KAGGLE_USERNAME --ref COMMIT --name embedder-v2
  uv run poe index-corpus --strategy page --docs all --key embedder-v2 \
      --model-dir data/models/embedder-v2/embedder \
      --vectors data/models/embedder-v2/vectors/embedder.npy
  uv run poe run-retrieval --collection fb_page_embedder-v2 --mode dense --setting understood --rewrite all
  uv run poe compare-family eval/results/retrieval/page_bge-small-dense-rw-multi-hyde-decompose-understood/dev \
      eval/results/retrieval/page_embedder-v2-dense-rw-multi-hyde-decompose-understood/dev --metric recall@10
  ```
