"""Train the classifier router on Kaggle: bge-small with LoRA, merged and exported to ONNX.

Step 7.2. Runs as a Kaggle kernel (`scripts/kaggle_router.py` pushes it): it downloads the
training set from the repository on GitHub at the commit written into REF below, fine-tunes
BAAI/bge-small-en-v1.5 with a classification head and LoRA adapters on the attention and
feed-forward layers, keeps the epoch with the best accuracy on the training set's validation split,
merges the adapters into the weights, and exports the model to ONNX. Writes to
/kaggle/working:

- model/: the merged model and its tokenizer (safetensors and tokenizer.json);
- adapter/: the LoRA adapters and the classification head, before merging;
- router.onnx: the same model for onnxruntime, with logits as its output;
- metrics.json: the configuration, each epoch's validation accuracy, the library versions,
  the exporter used, and a check that onnxruntime and PyTorch give the same logits.

The routing set itself is never read here: the classifier is evaluated on it afterwards,
on the machine that serves it.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PIP = [sys.executable, "-m", "pip", "-q"]
subprocess.run([*PIP, "install", "peft", "onnx", "onnxscript", "onnxruntime"], check=True)
# PEFT refuses a torchao older than it supports, even for LoRA, which doesn't use it; the
# Kaggle image ships an old one.
subprocess.run([*PIP, "uninstall", "-y", "torchao"], check=False)

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import peft  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402
from peft import LoraConfig, TaskType, get_peft_model  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

REF = "main"  # replaced with a commit by scripts/kaggle_router.py
REPO = "VinayakMokashi/filings-research-copilot"
DATA_URL = f"https://raw.githubusercontent.com/{REPO}/{REF}/data/reference/routing_train.jsonl"
BASE_MODEL = "BAAI/bge-small-en-v1.5"
ROUTES = ["doc", "data", "hybrid", "brief", "smalltalk", "decline"]
CONFIG = {
    "base_model": BASE_MODEL,
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.1,
    "target_modules": ["query", "key", "value", "dense"],
    "learning_rate": 5e-4,
    "epochs": 10,
    "batch_size": 32,
    "max_length": 96,
    "seed": 0,
}
OUT = Path("/kaggle/working")


def load_rows() -> list[dict[str, str]]:
    with urllib.request.urlopen(DATA_URL, timeout=60) as response:
        text = response.read().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def batches(rows: list[dict[str, str]], size: int, shuffle: bool, rng: random.Random):
    order = list(range(len(rows)))
    if shuffle:
        rng.shuffle(order)
    for start in range(0, len(order), size):
        yield [rows[i] for i in order[start : start + size]]


def main() -> None:
    random.seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])
    torch.manual_seed(CONFIG["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = load_rows()
    train = [row for row in rows if row["split"] == "train"]
    val = [row for row in rows if row["split"] == "val"]
    label = {route: index for index, route in enumerate(ROUTES)}

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, id2label=dict(enumerate(ROUTES)), label2id=label
    )
    lora = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=CONFIG["lora_r"],
        lora_alpha=CONFIG["lora_alpha"],
        lora_dropout=CONFIG["lora_dropout"],
        target_modules=CONFIG["target_modules"],
    )
    model = get_peft_model(model, lora).to(device)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    # Weight each class by the inverse of its share, so a rarer route isn't drowned out.
    counts = np.bincount([label[row["route"]] for row in train], minlength=len(ROUTES))
    weights = torch.tensor(counts.sum() / (len(ROUTES) * np.maximum(counts, 1)), dtype=torch.float)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights.to(device))
    optimiser = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=CONFIG["learning_rate"]
    )
    steps = CONFIG["epochs"] * -(-len(train) // CONFIG["batch_size"])
    schedule = torch.optim.lr_scheduler.OneCycleLR(
        optimiser, max_lr=CONFIG["learning_rate"], total_steps=steps
    )

    def encode(batch: list[dict[str, str]]) -> dict[str, torch.Tensor]:
        enc = tokenizer(
            [row["question"] for row in batch],
            padding=True,
            truncation=True,
            max_length=CONFIG["max_length"],
            return_tensors="pt",
        )
        return {key: value.to(device) for key, value in enc.items()}

    def accuracy(rows: list[dict[str, str]]) -> float:
        model.eval()
        right = 0
        with torch.no_grad():
            for batch in batches(rows, 128, False, random.Random(0)):
                logits = model(**encode(batch)).logits
                predicted = logits.argmax(dim=-1).tolist()
                truth = [label[row["route"]] for row in batch]
                right += sum(p == t for p, t in zip(predicted, truth, strict=True))
        return right / len(rows)

    history = []
    best, best_state = -1.0, None
    rng = random.Random(CONFIG["seed"])
    started = time.time()
    for epoch in range(1, CONFIG["epochs"] + 1):
        model.train()
        for batch in batches(train, CONFIG["batch_size"], True, rng):
            targets = torch.tensor([label[row["route"]] for row in batch], device=device)
            loss = loss_fn(model(**encode(batch)).logits, targets)
            loss.backward()
            optimiser.step()
            schedule.step()
            optimiser.zero_grad()
        score = accuracy(val)
        history.append({"epoch": epoch, "val_accuracy": round(score, 4)})
        print(f"epoch {epoch}: val accuracy {score:.4f}", flush=True)
        if score > best:
            best = score
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    seconds = time.time() - started
    model.load_state_dict(best_state)
    model.save_pretrained(OUT / "adapter")  # the LoRA adapters and the head on their own

    merged = model.merge_and_unload().to("cpu").eval()
    merged.save_pretrained(OUT / "model")
    tokenizer.save_pretrained(OUT / "model")

    metrics = {
        "config": CONFIG,
        "ref": REF,
        "train_rows": len(train),
        "val_rows": len(val),
        "trainable_parameters": trainable,
        "total_parameters": total,
        "device": device,
        "train_seconds": round(seconds, 1),
        "history": history,
        "best_val_accuracy": round(best, 4),
        "labels": ROUTES,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "peft": peft.__version__,
            "onnxruntime": ort.__version__,
        },
    }
    # Written before the export too, so a failed export still leaves the training's record.
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    exporter = export_onnx(tokenizer, [row["question"] for row in val[:8]], OUT / "router.onnx")
    # PyTorch and onnxruntime on a padded batch and on one question alone, as served.
    session = ort.InferenceSession(str(OUT / "router.onnx"))
    inputs = {item.name for item in session.get_inputs()}
    differences = []
    for questions in ([row["question"] for row in val[8:24]], [val[0]["question"]]):
        encoded = tokenizer(questions, padding=True, return_tensors="pt")
        with torch.no_grad():
            expected = merged(**encoded).logits.numpy()
        feeds = {name: tensor.numpy() for name, tensor in encoded.items() if name in inputs}
        actual = session.run(["logits"], feeds)[0]
        differences.append(float(np.max(np.abs(expected - actual))))
    metrics |= {"onnx_exporter": exporter, "onnx_max_abs_diff": max(differences)}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def export_onnx(tokenizer, questions: list[str], path: Path) -> str:
    """Export the saved model to ONNX, with eager attention, and name the exporter that worked.

    The TorchScript exporter reads dynamic_axes directly; the dynamo exporter, newer torch's
    default, is the second try.
    """
    model = AutoModelForSequenceClassification.from_pretrained(
        OUT / "model", attn_implementation="eager"
    ).eval()
    sample = tokenizer(questions, padding=True, return_tensors="pt")
    names = ["input_ids", "attention_mask", "token_type_ids"]
    options = {
        "input_names": names,
        "output_names": ["logits"],
        "dynamic_axes": {name: {0: "batch", 1: "tokens"} for name in names}
        | {"logits": {0: "batch"}},
        "opset_version": 17,
    }
    errors = []
    for exporter in ("torchscript", "dynamo"):
        # The dynamo exporter would put the weights in a file of their own by default.
        extra = {"dynamo": True, "external_data": False} if exporter == "dynamo" else {}
        try:
            torch.onnx.export(
                model,
                tuple(sample[name] for name in names),
                path,
                **({"dynamo": False} | extra),
                **options,
            )
            return exporter
        except Exception as exc:  # try the next exporter, and report both if both fail
            errors.append(f"{exporter}: {exc!r}"[:1000])
            print(f"The {exporter} exporter failed: {exc!r}", flush=True)
    raise RuntimeError("Both ONNX exporters failed: " + " | ".join(errors))


if __name__ == "__main__":
    main()
