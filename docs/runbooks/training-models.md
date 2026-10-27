# Training models

How to train the classifier router on a free Kaggle GPU, score it, and publish it on Hugging Face (step 7.2; [guide](../concepts/lora-classifier.md)), and how to train and evaluate a domain embedder (step 7.1; [guide](../concepts/contrastive-finetuning.md)). Training never runs on the laptop: the kernel trains, and the laptop serves the exported model on its CPU.

## Before you start

- **Kaggle:** an account with a verified phone number (GPUs need one), and an API token from the account's settings page ("Generate New Token"), saved as `~/.kaggle/access_token` with nothing but the token in it. The Kaggle CLI runs through `uvx`, so it is no dependency of the project: `uvx kaggle kernels list --mine` should answer (with "Not found" before your first kernel).
- **Hugging Face:** a fine-grained token with write access to your namespace, as `HF_TOKEN` in `.env`.
- **The training set** in `data/reference/routing_train.jsonl`, committed and pushed: the kernel downloads it from GitHub at the commit you name.

## Build the training set

```bash
FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b uv run poe generate-routing-train --per-route 400 --pause 0.3
```

A model writes questions route by route, the duplicate and leak filters drop what is too close to another question or to the routing set, and the LLM router labels the rest ([data card](../data/routing-train-set.md)). Each stage is resumable: run the same command again after a stop. The writer's batches go to `data/processed/routing-train/batches-<prompt version>.jsonl`, and the calls are cached in `data/cache/routing-train.jsonl` and `data/cache/router-teacher.jsonl`. `--pause` is the pause after each call: 3 seconds suits a free tier, 0.3 a paid one. About 45 minutes and $1 on Cerebras.

## Train on Kaggle

```bash
uv run poe kaggle-router --user KAGGLE_USERNAME --ref COMMIT --name router-v2
```

The script pins `kaggle/router/train_router.py` to the commit (`--ref`, a pushed commit that holds the training set), pushes it as a private kernel with a T4 GPU, polls its status every 30 seconds, and downloads its output to `data/models/<name>/` (git-ignored): the merged model in `model/`, the LoRA adapter in `adapter/`, `router.onnx`, `metrics.json`, the kernel's log, and the four files `ClassifierRouter` reads at the top of the folder. A run takes about two minutes, most of it the kernel's start.

Check `metrics.json`: `best_val_accuracy` is on the training set's own validation split (the teacher's labels), and `onnx_max_abs_diff` should be about 1e-5.

## Score it

```bash
uv run poe run-router --router classifier --model-dir data/models/router-v2 --run classifier-v2
uv run python scripts/simulate_cascade.py eval/results/routing/classifier-v2/dev \
    eval/results/routing/llm-gpt-oss-120b/dev --thresholds 0.9 0.99 --name cascade-classifier-v2
```

The first scores the classifier on the routing set's dev questions, with its CPU latency and the ONNX file's checksum. The second computes a cascade, the classifier's route when its confidence reaches a threshold and the LLM router's otherwise, from the two runs, with no model calls. At a milestone the classifier takes `--split test --allow-test` once.

## Publish it

```bash
uv run poe publish-router --model-dir data/models/router-v2 --repo NAMESPACE/NAME --dry-run
uv run poe publish-router --model-dir data/models/router-v2 --repo NAMESPACE/NAME
```

The dry run lists the files as they will be published: the model card (`docs/models/router-card.md`) as README.md, the merged model, `onnx/model.onnx`, the adapter and the training metrics. The second command creates the public repository if needed and uploads them.

## Train and evaluate a domain embedder

The embedder's training data are filing text, which the repository never commits, so the kernel reads them from a private Kaggle dataset instead of GitHub.

```bash
uv run poe kaggle-embedder --user KAGGLE_USERNAME --ref COMMIT --name embedder-v2
```

The script writes the data to `data/processed/embedder/` (the synthetic pairs with their validation split, the training filings' 480-token chunks, and the corpus's page chunks, gzipped and byte for byte the same on every run) and the manifest to `data/reference/embedder_data_manifest.json`. It uploads the folder as the private dataset `frc-embedder-data` when its checksums differ from the last upload's (recorded in `uploaded.json`), waits for Kaggle to process it, pushes `kaggle/embedder/train_embedder.py` as the kernel `frc-embedder` with a T4, and downloads its output to `data/models/<name>/`: the trained model in `model/`, the ONNX exports in `embedder/` and `base/`, the page vectors of both in `vectors/`, and `metrics.json`. About 30 minutes. `--prepare-only` writes the data and stops.

Check `metrics.json`: `base_val` against `chosen.val` shows what training did on held-out training filings, and `onnx` should show differences of about 1e-7.

Build a collection from the kernel's vectors, then run the retrieval evaluation on it:

```bash
uv run poe index-corpus --strategy page --docs all --key embedder-v2 \
    --model-dir data/models/embedder-v2/embedder \
    --vectors data/models/embedder-v2/vectors/embedder.npy
uv run poe run-retrieval --collection fb_page_embedder-v2 --mode dense --setting understood --rewrite all
```

The indexer embeds 16 chunks again on the CPU and stops if they differ from the stored vectors by more than 1e-3; the collection's card records the model's folder, so the retrieval run embeds its queries with the same model. The rewrites come from the cache, so the run makes no model calls. Compare the run with production's with `poe compare-family`, in each of the three settings ([report](../eval/domain-embedder.md)).

To try a collection in the doc agent, set `FRC_COLLECTION=fb_page_embedder-v2` in the run's environment.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `kaggle` answers 401 | The token file holds more than the token (an `export ...=` line, quotes): leave only the `KGAT_...` value |
| The kernel stops in `get_peft_model` with "an incompatible version of torchao" | PEFT refuses an old torchao even for LoRA; the kernel uninstalls it before importing PEFT |
| The kernel's status is `ERROR` | `uvx kaggle kernels output USER/frc-router -p DIR` downloads its log (JSON lines; the text is in each line's `data`) |
| The ONNX export fails | The kernel reloads the saved model with eager attention and tries the TorchScript exporter, then the dynamo one; the log names both errors |
| `publish-router` says HF_TOKEN isn't set | Add it to `.env`; the script reads it through the settings and never prints it |
| A status request answers 403 right after a dataset is created or a kernel pushed | Kaggle takes a minute to show a new one; the waits count it as not ready yet |
| `index-corpus` says the stored vectors differ from the CPU's | The vectors and `--model-dir` come from different models, or the export changed; use the folders from the same kernel run |
