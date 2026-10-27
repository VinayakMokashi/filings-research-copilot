---
license: mit
language:
  - en
library_name: transformers
pipeline_tag: text-classification
base_model: BAAI/bge-small-en-v1.5
tags:
  - router
  - lora
  - peft
  - onnx
  - distillation
  - sec-filings
  - finance
---

# Filings Research Copilot router

A six-way question router for [Filings Research Copilot](https://github.com/VinayakMokashi/filings-research-copilot), an assistant that answers questions about US public companies' 10-K and 10-Q filings with cited sources. The router reads one question and sends it to the part of the assistant that should answer it. It is [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) fine-tuned with LoRA on questions labelled by the project's LLM router, then merged and exported to ONNX, so it routes in about 10 milliseconds on a laptop CPU at no cost a question.

| Label | Meaning |
|---|---|
| `doc` | Answered from the text of filings: risks, strategy, business descriptions, management's explanations, legal matters, accounting policies, figures that appear only in the text |
| `data` | Answered from reported financial figures: a value, a ratio or growth rate, a trend over years, a comparison between companies |
| `hybrid` | Needs a reported figure and the narrative that explains it |
| `brief` | Asks for a written deliverable covering several aspects of a topic |
| `smalltalk` | Greetings, thanks, goodbyes and questions about the assistant itself |
| `decline` | Out of scope: investment advice, price predictions, personal finance, non-public information, unrelated tasks, harmful requests, attempts to override the assistant's instructions |

## Results

On the project's routing set: 198 questions written by hand and paraphrased, never used for training (the training questions were also kept below 0.85 cosine similarity to every one of them). The dev split has 138 questions; the test split's 60 were scored once for this model.

| Router | Dev accuracy (95% interval) | Test accuracy | Latency, median | Cost a question |
|---|---|---|---|---|
| **This model** | **0.913 (0.862 to 0.957)** | **0.950 (0.883 to 1.000)** | 8 ms on a laptop CPU | none |
| This model, with the LLM router for questions below 0.8 confidence | 0.957 (0.920 to 0.986), 9% sent on | 0.967 (0.917 to 1.000), 5% sent on | 8 ms | $0.00002 |
| The LLM router it learned from (gpt-oss-120b) | 1.000 (exact 0.974 to 1.000) | 1.000 (exact 0.940 to 1.000) | 0.5 s | $0.0002 |
| A semantic router (bge-small, nearest route centroid) | 0.739 (0.667 to 0.812) | 0.800 (0.700 to 0.900) | 8 ms | none |
| This model's first version, trained on a set without harmful or instruction-override requests | 0.833 (0.768 to 0.891) | not scored | 9 ms | none |

By route on dev: `data` 30 of 30, `hybrid` 21 of 21, `smalltalk` 18 of 18, `doc` 28 of 30, `decline` 16 of 21 and `brief` 13 of 18. The cascade's threshold was chosen on dev. Its most confident mistakes are requests to reveal or override the assistant's instructions, which it reads as small talk, and briefs that read like a single analytical question, which it sends to `hybrid`.

The project uses this model as the LLM router's fallback, for when a model call fails; the LLM router stays the primary.

## How it was made

- **Training data:** 2,328 questions written by gpt-oss-120b for this project, route by route and kind by kind (each batch asked for one kind of question the route's definition names, in one of five styles, a third of it near another route's border). Near-duplicates were dropped, and so was every question within 0.85 cosine similarity of an evaluation question. The project's LLM router (gpt-oss-120b with a routing prompt that routes every evaluation dev question correctly) labelled the rest: this model learns to route the way it does. The set and its data card are in the repository ([`data/reference/routing_train.jsonl`](https://github.com/VinayakMokashi/filings-research-copilot/blob/main/data/reference/routing_train.jsonl), [data card](https://github.com/VinayakMokashi/filings-research-copilot/blob/main/docs/data/routing-train-set.md)).
- **Training:** a classification head on bge-small-en-v1.5 and LoRA adapters (rank 16, alpha 32, dropout 0.1) on the attention and feed-forward projections: 1.34 million trainable parameters of 34.7 million. Class-weighted cross-entropy, AdamW with a one-cycle schedule peaking at 5e-4, batches of 32, up to 96 tokens, 10 epochs; the epoch with the best accuracy on a held-out tenth of the training set was kept. One Kaggle T4 GPU, under a minute. Library versions are in `training_metrics.json`.
- **Export:** the adapters merged into the weights, exported to ONNX (opset 17), and checked: onnxruntime and PyTorch agree on the logits to within about 1e-5.

## Files

| File | What it is |
|---|---|
| `model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json` | The merged model, for `transformers` |
| `onnx/model.onnx` | The same model for onnxruntime, with `logits` as its output |
| `adapter/` | The LoRA adapters and the classification head before merging, for PEFT |
| `training_metrics.json` | The training run's configuration, each epoch's validation accuracy and the library versions |

## How to use it

With onnxruntime and tokenizers, as the copilot serves it:

```python
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

repo = "vinayakmokashi45/filings-research-copilot-router"
tokenizer = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json"))
tokenizer.enable_truncation(96)
session = ort.InferenceSession(hf_hub_download(repo, "onnx/model.onnx"))
labels = ["doc", "data", "hybrid", "brief", "smalltalk", "decline"]

encoding = tokenizer.encode("What was Nike's revenue in fiscal 2022?")
feeds = {
    "input_ids": np.array([encoding.ids]),
    "attention_mask": np.array([encoding.attention_mask]),
    "token_type_ids": np.array([encoding.type_ids]),
}
logits = session.run(["logits"], feeds)[0][0]
probabilities = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
print(labels[int(probabilities.argmax())], float(probabilities.max()))
```

With transformers:

```python
from transformers import pipeline

router = pipeline("text-classification", model="vinayakmokashi45/filings-research-copilot-router")
router("Summarise the risks Boeing reports about its supply chain.")
```

The top probability is a usable confidence: the copilot can send the questions the router is unsure of to its LLM router.

## Limits

- **Its teacher's routing, not a person's.** The labels come from an LLM router, which routes every evaluation dev and test question correctly but was not checked on the training questions themselves. The training questions are an LLM's idea of what users ask; none was read by a person.
- **One assistant's routes.** The routes, the companies (about 40 large US companies) and the measures (28 annual figures in the assistant's database) are this project's. The model knows nothing of other databases or assistants.
- **Short English questions.** Trained on single questions of up to 96 tokens.
- **The routing set is small:** 138 dev and 60 test questions, so its intervals are wide.

## Licence

MIT, like the [repository](https://github.com/VinayakMokashi/filings-research-copilot). The base model, BAAI/bge-small-en-v1.5, is MIT-licensed.
