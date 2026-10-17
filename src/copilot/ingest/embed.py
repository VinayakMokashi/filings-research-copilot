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

`HashingDense` and `HashingSparse` are deterministic stand-ins for tests: texts that share
words get similar vectors, and nothing is downloaded.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
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
