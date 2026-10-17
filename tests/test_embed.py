"""Test embedders: deterministic, normalised, and closer for texts that share words."""

from __future__ import annotations

import numpy as np

from copilot.ingest.embed import HashingDense, HashingSparse, normalise


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
