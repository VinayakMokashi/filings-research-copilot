"""Embedding models for indexing and search (ADR-0010).

Dense vectors come from BAAI/bge-small-en-v1.5 (384 dimensions), run on the CPU through
FastEmbed's ONNX build. bge expects an instruction in front of short queries, which
`embed_query` adds; passages go in as they are. Sparse vectors are BM25 term weights from
FastEmbed's `Qdrant/bm25`; Qdrant applies the IDF part at query time, from its own corpus
statistics. The late-chunking experiment's model, jina-embeddings-v2-small-en, needs
token-level output and lives in `late_chunking.py`.

Texts are embedded one at a time: on the 8-core laptop CPU this project was built on, a
batch of 16 chunks ran at 5.5 chunks per second and single chunks at 9, because a batch is
padded to its longest text and spills out of the CPU caches.

`OnnxDense` serves a bge-style encoder exported to ONNX, such as the domain embedder that
step 7.1 fine-tunes from bge-small: CLS pooling and unit length over the model's last
hidden state, with bge's query instruction. A collection's index card names the model its
vectors came from, and `dense_for_card` loads the same model for its queries.

`HashingDense` and `HashingSparse` are deterministic stand-ins for tests: texts that share
words get similar vectors, and nothing is downloaded.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

BGE_MODEL = "BAAI/bge-small-en-v1.5"
BGE_DIM = 384
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
SPARSE_MODEL = "Qdrant/bm25"


@dataclass(frozen=True, slots=True)
class SparseVector:
    indices: list[int]
    values: list[float]


class DenseEmbedder(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]: ...

    def embed_query(self, text: str) -> NDArray[np.float32]: ...


class SparseEmbedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]: ...

    def embed_query(self, text: str) -> SparseVector: ...


def normalise(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    """Rows scaled to unit length (all-zero rows stay zero)."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    scaled: NDArray[np.float32] = (vectors / np.maximum(norms, 1e-12)).astype(np.float32)
    return scaled


class FastEmbedDense:
    """bge-small through FastEmbed; downloaded on first use and cached in `cache_dir`."""

    key = "bge-small"
    dim = BGE_DIM

    def __init__(
        self, *, batch_size: int = 1, threads: int | None = None, cache_dir: Path | None = None
    ) -> None:
        from fastembed import TextEmbedding

        self._batch_size = batch_size
        self._model: Any = TextEmbedding(
            BGE_MODEL, threads=threads, cache_dir=str(cache_dir) if cache_dir else None
        )

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = list(self._model.embed(list(texts), batch_size=self._batch_size))
        return np.asarray(vectors, dtype=np.float32)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        vector: NDArray[np.float32] = self.embed_documents([BGE_QUERY_INSTRUCTION + text])[0]
        return vector


# Texts in, the encoder's last hidden state out: one row of token vectors a text.
Encoder = Callable[[Sequence[str]], NDArray[np.float32]]
MAX_TOKENS = 512  # bge's limit; chunks are cut to 480 of its tokens, so none is truncated


def onnx_encoder(directory: Path, max_tokens: int = MAX_TOKENS) -> Encoder:
    """The directory's ONNX encoder (model.onnx) and its tokenizer (tokenizer.json)."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    tokenizer.enable_truncation(max_tokens)
    pad = tokenizer.token_to_id("[PAD]")
    tokenizer.enable_padding(pad_id=0 if pad is None else pad, pad_token="[PAD]")
    session = ort.InferenceSession(
        str(directory / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    names = {item.name for item in session.get_inputs()}

    def encode(texts: Sequence[str]) -> NDArray[np.float32]:
        encodings = tokenizer.encode_batch(list(texts))
        feeds: dict[str, Any] = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
        }
        hidden = session.run(["last_hidden_state"], {k: v for k, v in feeds.items() if k in names})
        return np.asarray(hidden[0], dtype=np.float32)

    return encode


class OnnxDense:
    """A bge-style encoder exported to ONNX, on the CPU; see the module docstring."""

    def __init__(
        self,
        encoder: Encoder,
        *,
        key: str,
        dim: int,
        query_instruction: str = BGE_QUERY_INSTRUCTION,
    ) -> None:
        self._encoder = encoder
        self.key = key
        self.dim = dim
        self._instruction = query_instruction

    @classmethod
    def load(cls, directory: Path, key: str | None = None) -> OnnxDense:
        """The encoder in `directory`: model.onnx, tokenizer.json and config.json."""
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        return cls(
            onnx_encoder(directory), key=key or directory.name, dim=int(config["hidden_size"])
        )

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # One text at a time, as FastEmbedDense does: on this CPU, faster than padded batches.
        rows = [self._encoder([text])[0, 0] for text in texts]  # each text's CLS vector
        return normalise(np.asarray(rows, dtype=np.float32))

    def embed_query(self, text: str) -> NDArray[np.float32]:
        vector: NDArray[np.float32] = self.embed_documents([self._instruction + text])[0]
        return vector


def dense_for_card(card: Mapping[str, Any], data_dir: Path) -> DenseEmbedder:
    """The embedder for a collection's queries, as its index card names it.

    A card's `model_dir` is relative to the data directory, so the same card serves a local
    run and a container that mounts the data elsewhere.
    """
    dense = card["dense"]
    if dense["query_model"] == "bge-small":
        return FastEmbedDense(cache_dir=data_dir / "models")
    if dense["query_model"] == "onnx":
        return OnnxDense.load(data_dir / dense["model_dir"], key=str(dense["key"]))
    raise ValueError(f"No query embedder for {dense['query_model']!r}.")


class FastEmbedBM25:
    """BM25 sparse vectors: term-frequency weights here, IDF in Qdrant."""

    def __init__(self, *, cache_dir: Path | None = None) -> None:
        from fastembed import SparseTextEmbedding

        self._model: Any = SparseTextEmbedding(
            SPARSE_MODEL, cache_dir=str(cache_dir) if cache_dir else None
        )

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [_sparse(vector) for vector in self._model.embed(list(texts))]

    def embed_query(self, text: str) -> SparseVector:
        return _sparse(next(iter(self._model.query_embed(text))))


def _sparse(vector: Any) -> SparseVector:
    return SparseVector(
        indices=[int(i) for i in vector.indices], values=[float(v) for v in vector.values]
    )


_WORD = re.compile(r"[a-z0-9]+")


def _bucket(word: str, size: int) -> int:
    return int.from_bytes(hashlib.blake2b(word.encode(), digest_size=4).digest(), "big") % size


@dataclass(frozen=True, slots=True)
class HashingDense:
    """A deterministic bag-of-words embedder for tests."""

    dim: int = 64
    key: str = "hashing"

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in _WORD.findall(text.lower()):
                vectors[row, _bucket(word, self.dim)] += 1.0
        return normalise(vectors)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        vector: NDArray[np.float32] = self.embed_documents([text])[0]
        return vector


@dataclass(frozen=True, slots=True)
class HashingSparse:
    """Word counts as a sparse vector, for tests."""

    size: int = 1 << 20

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> SparseVector:
        counts: dict[int, float] = {}
        for word in _WORD.findall(text.lower()):
            index = _bucket(word, self.size)
            counts[index] = counts.get(index, 0.0) + 1.0
        ordered = sorted(counts)
        return SparseVector(indices=ordered, values=[counts[i] for i in ordered])
