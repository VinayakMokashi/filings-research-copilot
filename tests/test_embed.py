"""Test embedders: deterministic, normalised, and closer for texts that share words."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from copilot.ingest import embed
from copilot.ingest.embed import (
    BGE_QUERY_INSTRUCTION,
    HashingDense,
    HashingSparse,
    OnnxDense,
    dense_for_card,
    normalise,
)


def test_hashing_dense_is_normalised_and_deterministic() -> None:
    vectors = HashingDense(dim=32).embed_documents(["Revenue grew", "Revenue grew", ""])

    assert vectors.shape == (3, 32)
    assert vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors[:2], axis=1), 1.0)
    assert np.array_equal(vectors[0], vectors[1])
    assert not vectors[2].any()


def test_hashing_dense_puts_texts_with_shared_words_closer() -> None:
    model = HashingDense()
    query = model.embed_query("operating income")
    near, far = model.embed_documents(["Operating income rose", "Litigation risk factors"])

    assert float(query @ near) > float(query @ far)


def test_hashing_sparse_counts_words() -> None:
    vector = HashingSparse().embed_query("Cash and cash equivalents")

    assert sorted(vector.values) == [1.0, 1.0, 2.0]
    assert vector.indices == sorted(vector.indices)


def test_normalise_scales_rows_and_keeps_zero_rows() -> None:
    out = normalise(np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32))

    assert np.allclose(out, [[0.6, 0.8], [0.0, 0.0]])
    assert out.dtype == np.float32


class FakeEncoder:
    """Hidden states whose first token's vector is set per text, recording what came in."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.seen += list(texts)
        hidden = np.ones((len(texts), 5, 2), dtype=np.float32)  # every other token: [1, 1]
        for row, text in enumerate(texts):
            hidden[row, 0] = [3.0, 4.0] if "revenue" in text else [0.0, 2.0]
        return hidden


def test_onnx_dense_pools_the_first_token_to_unit_length() -> None:
    model = OnnxDense(FakeEncoder(), key="tuned", dim=2)

    vectors = model.embed_documents(["revenue grew", "a risk"])

    assert np.allclose(vectors, [[0.6, 0.8], [0.0, 1.0]])
    assert vectors.dtype == np.float32
    assert model.embed_documents([]).shape == (0, 2)


def test_onnx_dense_adds_the_query_instruction_to_queries_only() -> None:
    encoder = FakeEncoder()
    model = OnnxDense(encoder, key="tuned", dim=2)

    model.embed_query("revenue")
    model.embed_documents(["revenue"])

    assert encoder.seen == [BGE_QUERY_INSTRUCTION + "revenue", "revenue"]


def test_dense_for_card_loads_the_model_the_card_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    loaded: list[tuple[Path, str | None]] = []

    def fake_load(directory: Path, key: str | None = None) -> OnnxDense:
        loaded.append((directory, key))
        return OnnxDense(FakeEncoder(), key=key or "x", dim=2)

    monkeypatch.setattr(embed.OnnxDense, "load", staticmethod(fake_load))
    card = {"dense": {"query_model": "onnx", "key": "embedder-v1", "model_dir": "models/e/onnx"}}

    model = dense_for_card(card, tmp_path)

    assert model.key == "embedder-v1"
    assert loaded == [(tmp_path / "models/e/onnx", "embedder-v1")]
    with pytest.raises(ValueError, match="No query embedder"):
        dense_for_card({"dense": {"query_model": "word2vec"}}, tmp_path)
