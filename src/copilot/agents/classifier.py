"""A fine-tuned classifier as the router, served on the CPU with onnxruntime (step 7.2).

The LLM router decides well, but every question costs a model call: about half a second
and $0.0002 (ADR-0017). A small encoder fine-tuned on its decisions answers in
milliseconds on the CPU, at no cost a question. The training questions come from
`copilot.agents.router_training`, and `kaggle/router/train_router.py` trains the model.

`ClassifierRouter` returns the route with the highest probability, with that probability
as `confidence`, so a cascade can send the questions it is unsure of to the LLM router.
A model directory holds the ONNX export (`router.onnx`), its tokenizer (`tokenizer.json`)
and `config.json`, whose `id2label` names the routes in the model's output order.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from copilot.agents.router import ROUTES, Route, RouteDecision

# Questions in, one row of logits a question out, in the order of the model's labels.
Scorer = Callable[[Sequence[str]], NDArray[np.float32]]
MAX_TOKENS = 96  # as in training


def softmax(logits: NDArray[np.float32]) -> NDArray[np.float32]:
    """Row-wise probabilities from logits."""
    shifted = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probabilities: NDArray[np.float32] = (shifted / shifted.sum(axis=-1, keepdims=True)).astype(
        np.float32
    )
    return probabilities


def read_labels(directory: Path) -> list[Route]:
    """The routes in the model's output order, from its config.json."""
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    id2label: dict[str, str] = config["id2label"]
    labels = [id2label[str(index)] for index in range(len(id2label))]
    known: dict[str, Route] = {route: route for route in ROUTES}
    unknown = sorted(set(labels) - set(known))
    if unknown:
        raise ValueError(f"The model names routes the copilot doesn't have: {unknown}.")
    return [known[label] for label in labels]


def onnx_scorer(directory: Path) -> Scorer:
    """Score questions with the directory's ONNX model and tokenizer."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    tokenizer.enable_truncation(MAX_TOKENS)
    pad = tokenizer.token_to_id("[PAD]")
    tokenizer.enable_padding(pad_id=0 if pad is None else pad, pad_token="[PAD]")
    session = ort.InferenceSession(
        str(directory / "router.onnx"), providers=["CPUExecutionProvider"]
    )
    names = {item.name for item in session.get_inputs()}

    def score(questions: Sequence[str]) -> NDArray[np.float32]:
        encodings = tokenizer.encode_batch(list(questions))
        feeds: dict[str, Any] = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
        }
        logits = session.run(["logits"], {k: v for k, v in feeds.items() if k in names})[0]
        return np.asarray(logits, dtype=np.float32)

    return score


class ClassifierRouter:
    """Routes with a fine-tuned classifier; see the module docstring."""

    name = "classifier"

    def __init__(self, scorer: Scorer, labels: Sequence[Route], model: str = "classifier") -> None:
        self._scorer = scorer
        self._labels = list(labels)
        self._model = model

    @classmethod
    def load(cls, directory: Path, model: str | None = None) -> ClassifierRouter:
        """The router over a model directory (see the module docstring)."""
        return cls(onnx_scorer(directory), read_labels(directory), model or directory.name)

    def route(self, question: str) -> RouteDecision:
        started = time.perf_counter()
        probabilities = softmax(self._scorer([question]))[0]
        best = int(np.argmax(probabilities))
        return RouteDecision(
            route=self._labels[best],
            router=self.name,
            confidence=float(probabilities[best]),
            scores={
                label: round(float(p), 4)
                for label, p in zip(self._labels, probabilities, strict=True)
            },
            model=self._model,
            latency_s=time.perf_counter() - started,
            cost_usd=0.0,
        )
