"""Fine-tune bge-small on the synthetic pairs on Kaggle: MNRL with mined hard negatives.

Step 7.1. Runs as a Kaggle kernel (`scripts/kaggle_embedder.py` pushes it) and reads its data
from a private Kaggle dataset, because the data hold filing text that the repository never
commits (FinanceBench's filings, CC BY-NC 4.0); `copilot.training.embedder` writes them:

- pairs.jsonl.gz: the synthetic questions, each with the chunk that answers it and a split
  (validation holds every pair of about a tenth of the training filings);
- chunks.jsonl.gz: every 480-token chunk of the training filings;
- pages.jsonl.gz: the page chunks of the 84 filings behind FinanceBench's questions.

1. Mine hard negatives with the base model: for each pair, the chunks of its own filing that
   rank highest for its question, leaving out the positive, its neighbours (chunks overlap by
   64 tokens) and any chunk scoring at least 95% of the positive's score, which may well
   answer the question too (positive-aware mining, as in NV-Retriever).
2. Train the whole model with MultipleNegativesRankingLoss: each question against its
   positive, its hard negatives and every other passage in the batch, where a passage that is
   the question's positive or a neighbour of it doesn't count as a negative. A small grid of
   learning rates, up to three epochs each; the epoch with the best MRR@10 on validation,
   where a question's chunk is ranked among all the chunks of its filing, is kept.
3. Export the trained model and, as a control, the base model to ONNX with the same exporter
   (the last hidden state as output; CLS pooling and unit length happen outside), and check
   onnxruntime against PyTorch.
4. Embed the corpus's page chunks with both models in fp32, for the retrieval evaluation that
   runs afterwards on the machine that serves the model.

Writes to /kaggle/working: model/ (the trained model and tokenizer, with sentence-transformers'
module files), embedder/ and base/ (model.onnx, tokenizer.json and config.json each),
vectors/ (embedder.npy, base.npy and chunk_ids.json, in pages.jsonl.gz's order) and
metrics.json (written after training too, so a failed export still leaves the record).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PIP = [sys.executable, "-m", "pip", "-q"]
subprocess.run([*PIP, "install", "onnx", "onnxscript", "onnxruntime"], check=True)

import huggingface_hub  # noqa: E402
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402, N812
import transformers  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

REF = "main"  # the commit of this code, written in by scripts/kaggle_embedder.py
BASE_MODEL = "BAAI/bge-small-en-v1.5"
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
CONFIG = {
    "base_model": BASE_MODEL,
    "loss": "MultipleNegativesRankingLoss",
    "scale": 20.0,
    "batch_size": 32,
    "hard_negatives": 3,
    "negative_margin": 0.95,
    "neighbour_window": 1,
    "learning_rates": [1e-5, 2e-5, 5e-5],
    "epochs": 3,
    "warmup_share": 0.1,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "query_max_tokens": 96,
    "passage_max_tokens": 512,
    "pooling": "cls",
    "query_instruction": QUERY_INSTRUCTION,
    "seed": 0,
}
SENTENCE_TRANSFORMERS_FILES = [
    "modules.json",
    "config_sentence_transformers.json",
    "sentence_bert_config.json",
    "1_Pooling/config.json",
]
INPUT = Path("/kaggle/input")
OUT = Path("/kaggle/working")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def log(message: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)


def read_rows(name: str) -> tuple[list[dict], str]:
    """A data file's rows and the SHA-256 of its uncompressed text, wherever Kaggle mounted it."""
    for candidate in (name, name.removesuffix(".gz")):
        found = sorted(INPUT.rglob(candidate))
        if found:
            raw = found[0].read_bytes()
            text = gzip.decompress(raw) if found[0].suffix == ".gz" else raw
            rows = [json.loads(line) for line in text.decode("utf-8").splitlines() if line]
            return rows, hashlib.sha256(text).hexdigest()
    raise FileNotFoundError(f"No {name} under {INPUT}")


def tokenize(tokenizer, texts: list[str], max_tokens: int) -> dict[str, torch.Tensor]:
    encoded = tokenizer(
        texts, padding=True, truncation=True, max_length=max_tokens, return_tensors="pt"
    )
    return {key: value.to(DEVICE) for key, value in encoded.items()}


def cls_vectors(model, encoded: dict[str, torch.Tensor]) -> torch.Tensor:
    """CLS pooling and unit length, as bge is trained and served."""
    return F.normalize(model(**encoded).last_hidden_state[:, 0].float(), dim=-1)


def embed(model, tokenizer, texts: list[str], max_tokens: int, fp16: bool = True) -> torch.Tensor:
    """Unit vectors for `texts`, on the CPU; batches sorted by length to pad less."""
    model.eval()
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    out = torch.empty(len(texts), model.config.hidden_size)
    with torch.no_grad():
        for start in range(0, len(order), 128):
            rows = order[start : start + 128]
            encoded = tokenize(tokenizer, [texts[i] for i in rows], max_tokens)
            with torch.autocast("cuda", dtype=torch.float16, enabled=fp16 and DEVICE == "cuda"):
                out[rows] = cls_vectors(model, encoded).cpu()
    return out


def query_texts(pairs: list[dict]) -> list[str]:
    return [QUERY_INSTRUCTION + pair["question"] for pair in pairs]


class Corpus:
    """The training filings' chunks, by filing and by id."""

    def __init__(self, chunks: list[dict]) -> None:
        self.chunks = chunks
        self.row = {chunk["chunk_id"]: row for row, chunk in enumerate(chunks)}
        self.by_doc: dict[str, list[int]] = {}
        for row, chunk in enumerate(chunks):
            self.by_doc.setdefault(chunk["doc_name"], []).append(row)

    def neighbours(self, pair: dict, window: int) -> set[str]:
        """The pair's chunk and those within `window` places of it in its filing."""
        return {
            self.chunks[row]["chunk_id"]
            for row in self.by_doc[pair["doc_name"]]
            if abs(self.chunks[row]["chunk_index"] - pair["chunk_index"]) <= window
        }


def ranks(vectors: torch.Tensor, corpus: Corpus, pairs: list[dict], queries: torch.Tensor):
    """Each pair's chunks of its filing by score, and the 0-based rank of its own chunk."""
    for pair, query in zip(pairs, queries, strict=True):
        rows = corpus.by_doc[pair["doc_name"]]
        scores = vectors[rows] @ query
        order = [rows[i] for i in torch.argsort(scores, descending=True).tolist()]
        by_row = dict(zip(rows, scores.tolist(), strict=True))
        yield pair, order, by_row, order.index(corpus.row[pair["chunk_id"]])


def mine(corpus: Corpus, vectors: torch.Tensor, pairs: list[dict], queries: torch.Tensor):
    """Hard negatives for each pair (chunk ids), and what mining found."""
    k, margin = CONFIG["hard_negatives"], CONFIG["negative_margin"]
    rng = random.Random(CONFIG["seed"])
    negatives: dict[int, list[str]] = {}
    skipped_margin = filled = 0
    positive_ranks = []
    for pair, order, scores, rank in ranks(vectors, corpus, pairs, queries):
        positive_ranks.append(rank)
        excluded = corpus.neighbours(pair, CONFIG["neighbour_window"])
        threshold = margin * scores[corpus.row[pair["chunk_id"]]]
        picked: list[str] = []
        for row in order:
            chunk_id = corpus.chunks[row]["chunk_id"]
            if chunk_id in excluded:
                continue
            if scores[row] >= threshold:
                skipped_margin += 1
                continue
            picked.append(chunk_id)
            if len(picked) == k:
                break
        while len(picked) < k:  # a short filing: easy negatives from another filing
            other = rng.choice(corpus.chunks)
            if other["doc_name"] != pair["doc_name"]:
                picked.append(other["chunk_id"])
                filled += 1
        negatives[pair["pair_id"]] = picked
    stats = {
        "pairs": len(pairs),
        "negatives_per_pair": k,
        "skipped_over_margin": skipped_margin,
        "filled_from_other_filings": filled,
        "base_positive_rank_median": float(np.median(positive_ranks)) + 1,
        "base_positive_top1_share": round(sum(r == 0 for r in positive_ranks) / len(pairs), 4),
    }
    return negatives, stats


def validate(model, tokenizer, corpus: Corpus, pairs: list[dict]) -> dict[str, float]:
    """MRR@10 and recall@10 of each validation question's chunk among its filing's chunks."""
    docs = sorted({pair["doc_name"] for pair in pairs})
    rows = [row for doc in docs for row in corpus.by_doc[doc]]
    vectors = torch.zeros(len(corpus.chunks), model.config.hidden_size)
    texts = [corpus.chunks[row]["text"] for row in rows]
    vectors[rows] = embed(model, tokenizer, texts, CONFIG["passage_max_tokens"])
    queries = embed(model, tokenizer, query_texts(pairs), CONFIG["query_max_tokens"])
    found = [rank for *_, rank in ranks(vectors, corpus, pairs, queries)]
    return {
        "mrr@10": round(sum(1 / (r + 1) for r in found if r < 10) / len(found), 4),
        "recall@10": round(sum(r < 10 for r in found) / len(found), 4),
        "pairs": len(found),
    }


def train(lr, tokenizer, corpus, train_pairs, val_pairs, negatives):
    """One learning rate: the best epoch's weights, its score and every epoch's record."""
    torch.manual_seed(CONFIG["seed"])
    rng = random.Random(CONFIG["seed"])
    model = AutoModel.from_pretrained(BASE_MODEL).to(DEVICE)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    size = CONFIG["batch_size"]
    steps = CONFIG["epochs"] * math.ceil(len(train_pairs) / size)
    warmup = max(1, int(steps * CONFIG["warmup_share"]))
    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=CONFIG["weight_decay"])
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimiser,
        lambda step: (
            (step + 1) / warmup
            if step < warmup
            else max(0.0, (steps - step) / max(1, steps - warmup))
        ),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE == "cuda")
    excluded = {
        pair["pair_id"]: corpus.neighbours(pair, CONFIG["neighbour_window"]) for pair in train_pairs
    }
    history, best, best_state = [], -1.0, None
    for epoch in range(1, CONFIG["epochs"] + 1):
        model.train()
        order = train_pairs[:]
        rng.shuffle(order)
        losses = []
        for start in range(0, len(order), size):
            batch = order[start : start + size]
            columns = [pair["chunk_id"] for pair in batch] + [
                chunk_id for pair in batch for chunk_id in negatives[pair["pair_id"]]
            ]
            passages = [corpus.chunks[corpus.row[chunk_id]]["text"] for chunk_id in columns]
            with torch.autocast("cuda", dtype=torch.float16, enabled=DEVICE == "cuda"):
                queries = cls_vectors(
                    model, tokenize(tokenizer, query_texts(batch), CONFIG["query_max_tokens"])
                )
                documents = cls_vectors(
                    model, tokenize(tokenizer, passages, CONFIG["passage_max_tokens"])
                )
            scores = CONFIG["scale"] * queries.float() @ documents.float().T
            mask = torch.tensor(
                [
                    [
                        col != row and column in excluded[pair["pair_id"]]
                        for col, column in enumerate(columns)
                    ]
                    for row, pair in enumerate(batch)
                ],
                device=DEVICE,
            )
            scores = scores.masked_fill(mask, -1e9)
            loss = F.cross_entropy(scores, torch.arange(len(batch), device=DEVICE))
            scaler.scale(loss).backward()
            scaler.unscale_(optimiser)
            torch.nn.utils.clip_grad_norm_(model.parameters(), CONFIG["max_grad_norm"])
            scaler.step(optimiser)
            scaler.update()
            schedule.step()
            optimiser.zero_grad(set_to_none=True)
            losses.append(loss.item())
        score = validate(model, tokenizer, corpus, val_pairs)
        history.append(
            {"lr": lr, "epoch": epoch, "train_loss": round(float(np.mean(losses)), 4), **score}
        )
        log(f"lr {lr:g} epoch {epoch}: loss {np.mean(losses):.4f}, val {score}")
        if score["mrr@10"] > best:
            best = score["mrr@10"]
            best_state = {k: v.detach().to("cpu").clone() for k, v in model.state_dict().items()}
    del model
    torch.cuda.empty_cache()
    return best_state, best, history


class LastHidden(torch.nn.Module):
    """The encoder with its last hidden state as the one output, for the ONNX export."""

    def __init__(self, model) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask, token_type_ids):
        return self.model(
            input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids
        ).last_hidden_state


def export_onnx(source: str | Path, tokenizer, texts: list[str], path: Path) -> str:
    """Export a saved model to ONNX with eager attention; the exporter that worked.

    The TorchScript exporter reads dynamic_axes directly; the dynamo exporter, newer torch's
    default, is the second try.
    """
    model = LastHidden(AutoModel.from_pretrained(source, attn_implementation="eager").eval())
    sample = tokenizer(texts, padding=True, return_tensors="pt")
    names = ["input_ids", "attention_mask", "token_type_ids"]
    options = {
        "input_names": names,
        "output_names": ["last_hidden_state"],
        "dynamic_axes": {name: {0: "batch", 1: "tokens"} for name in names}
        | {"last_hidden_state": {0: "batch", 1: "tokens"}},
        "opset_version": 17,
    }
    errors = []
    for exporter in ("torchscript", "dynamo"):
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
            log(f"The {exporter} exporter failed: {exc!r}")
    raise RuntimeError("Both ONNX exporters failed: " + " | ".join(errors))


def onnx_difference(source: str | Path, tokenizer, path: Path, texts: list[str]) -> float:
    """The largest difference between onnxruntime's and PyTorch's unit vectors."""
    model = AutoModel.from_pretrained(source).eval()
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inputs = {item.name for item in session.get_inputs()}
    differences = []
    for batch in (texts[:8], texts[8:9]):
        encoded = tokenizer(
            batch, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        with torch.no_grad():
            expected = F.normalize(model(**encoded).last_hidden_state[:, 0], dim=-1).numpy()
        feeds = {name: tensor.numpy() for name, tensor in encoded.items() if name in inputs}
        hidden = session.run(["last_hidden_state"], feeds)[0][:, 0]
        actual = hidden / np.linalg.norm(hidden, axis=-1, keepdims=True)
        differences.append(float(np.max(np.abs(expected - actual))))
    return max(differences)


def model_folder(folder: Path, onnx_path: Path, config_source: str | Path, tokenizer) -> None:
    """A folder the project's ONNX embedder loads: model.onnx, tokenizer.json, config.json."""
    folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(onnx_path), folder / "model.onnx")
    tokenizer.save_pretrained(folder)
    transformers.AutoConfig.from_pretrained(config_source).save_pretrained(folder)


def main() -> None:
    random.seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])
    torch.manual_seed(CONFIG["seed"])
    started = time.time()
    pairs, pairs_sha = read_rows("pairs.jsonl.gz")
    chunks, chunks_sha = read_rows("chunks.jsonl.gz")
    pages, pages_sha = read_rows("pages.jsonl.gz")
    train_pairs = [pair for pair in pairs if pair["split"] == "train"]
    val_pairs = [pair for pair in pairs if pair["split"] == "val"]
    log(
        f"{len(train_pairs)} train and {len(val_pairs)} val pairs, {len(chunks)} chunks, "
        f"{len(pages)} pages, on {DEVICE}"
    )
    corpus = Corpus(chunks)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    base = AutoModel.from_pretrained(BASE_MODEL).to(DEVICE)
    vectors = embed(base, tokenizer, [c["text"] for c in chunks], CONFIG["passage_max_tokens"])
    queries = embed(base, tokenizer, query_texts(pairs), CONFIG["query_max_tokens"])
    negatives, mining = mine(corpus, vectors, pairs, queries)
    log(f"mined: {mining}")
    base_val = validate(base, tokenizer, corpus, val_pairs)
    log(f"base model on val: {base_val}")
    del base, vectors
    torch.cuda.empty_cache()

    history, best, best_state, best_lr = [], -1.0, None, None
    train_started = time.time()
    for lr in CONFIG["learning_rates"]:
        state, score, records = train(lr, tokenizer, corpus, train_pairs, val_pairs, negatives)
        history += records
        if score > best:
            best, best_state, best_lr = score, state, lr
    train_seconds = time.time() - train_started
    chosen = max(history, key=lambda record: record["mrr@10"])

    model = AutoModel.from_pretrained(BASE_MODEL)
    model.load_state_dict(best_state)
    model.save_pretrained(OUT / "model")
    tokenizer.save_pretrained(OUT / "model")
    extras = huggingface_hub.snapshot_download(
        BASE_MODEL, allow_patterns=SENTENCE_TRANSFORMERS_FILES
    )
    for name in SENTENCE_TRANSFORMERS_FILES:
        if (Path(extras) / name).exists():
            (OUT / "model" / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(extras) / name, OUT / "model" / name)

    metrics = {
        "config": CONFIG,
        "ref": REF,
        "data": {
            "pairs": {"rows": len(pairs), "sha256": pairs_sha},
            "chunks": {"rows": len(chunks), "sha256": chunks_sha},
            "pages": {"rows": len(pages), "sha256": pages_sha},
            "train_pairs": len(train_pairs),
            "val_pairs": len(val_pairs),
        },
        "device": torch.cuda.get_device_name(0) if DEVICE == "cuda" else "cpu",
        "parameters": sum(p.numel() for p in model.parameters()),
        "mining": mining,
        "base_val": base_val,
        "history": history,
        "chosen": {"lr": best_lr, "epoch": chosen["epoch"], "val": chosen},
        "train_seconds": round(train_seconds, 1),
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "onnxruntime": ort.__version__,
            "huggingface_hub": huggingface_hub.__version__,
        },
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    log(f"chosen lr {best_lr:g}, epoch {chosen['epoch']}: val {chosen}")

    samples = [page["text"] for page in pages[:: max(1, len(pages) // 9)][:9]]
    exports = {}
    for name, source in (("embedder", OUT / "model"), ("base", BASE_MODEL)):
        path = OUT / f"{name}.onnx"
        exporter = export_onnx(source, tokenizer, samples[:4], path)
        difference = onnx_difference(source, tokenizer, path, samples)
        model_folder(OUT / name, path, source, tokenizer)
        exports[name] = {"exporter": exporter, "max_abs_diff": difference}
        log(f"{name}: exported with {exporter}, difference {difference:.2e}")
    metrics["onnx"] = exports

    (OUT / "vectors").mkdir(exist_ok=True)
    texts = [page["text"] for page in pages]
    timings = {}
    for name, source in (("embedder", OUT / "model"), ("base", BASE_MODEL)):
        model = AutoModel.from_pretrained(source).to(DEVICE)
        begun = time.time()
        vectors = embed(model, tokenizer, texts, CONFIG["passage_max_tokens"], fp16=False)
        timings[name] = round(time.time() - begun, 1)
        np.save(OUT / "vectors" / f"{name}.npy", vectors.numpy().astype(np.float32))
        del model
        torch.cuda.empty_cache()
        log(f"embedded {len(texts)} pages with {name} in {timings[name]} s")
    (OUT / "vectors" / "chunk_ids.json").write_text(
        json.dumps([page["chunk_id"] for page in pages]), encoding="utf-8"
    )
    metrics["page_vectors"] = {"rows": len(pages), "fp32": True, "seconds": timings}
    metrics["total_seconds"] = round(time.time() - started, 1)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
