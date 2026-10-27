"""Models on the Hugging Face Hub: the files a trained router publishes, in the Hub's layout.

`poe kaggle-router` downloads a training run's output to data/models/<name>: the merged
model in model/, the ONNX export, the LoRA adapter and the metrics. `stage` copies them,
with the model card, into the layout the Hub's tools read, and `poe publish-router`
uploads the result.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Published path -> path inside the model folder
ROUTER_LAYOUT: dict[str, str] = {
    # the merged model, which AutoModelForSequenceClassification.from_pretrained loads
    "config.json": "model/config.json",
    "model.safetensors": "model/model.safetensors",
    "tokenizer.json": "model/tokenizer.json",
    "tokenizer_config.json": "model/tokenizer_config.json",
    # the export ClassifierRouter serves on the CPU
    "onnx/model.onnx": "router.onnx",
    # the LoRA adapters and the head before merging, for PEFT
    "adapter/adapter_config.json": "adapter/adapter_config.json",
    "adapter/adapter_model.safetensors": "adapter/adapter_model.safetensors",
    # the training run's configuration, accuracy and library versions
    "training_metrics.json": "metrics.json",
}


def stage(
    model_dir: Path, card: Path, out: Path, layout: dict[str, str] = ROUTER_LAYOUT
) -> list[str]:
    """Copy the card (as README.md) and the model's files into `out`; the published paths.

    FileNotFoundError names whatever is missing, before anything is copied.
    """
    missing = [source for source in layout.values() if not (model_dir / source).exists()]
    if not card.exists():
        missing.append(str(card))
    if missing:
        raise FileNotFoundError(f"Missing: {', '.join(missing)}")
    (out / "README.md").write_bytes(card.read_bytes())
    for published, source in layout.items():
        target = out / published
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model_dir / source, target)
    return ["README.md", *layout]
