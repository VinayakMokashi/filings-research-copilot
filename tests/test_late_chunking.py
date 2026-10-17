"""Late chunking: window plan, token ownership, span mapping and pooling."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from copilot.ingest.late_chunking import ownership, plan_windows, pool_late, token_range


def test_windows_cover_the_document_with_the_overlap() -> None:
    assert plan_windows(10, 4, 2) == [(0, 4), (2, 6), (4, 8), (6, 10)]
    assert plan_windows(9, 4, 1) == [(0, 4), (3, 7), (6, 9)]
    assert plan_windows(3, 4, 2) == [(0, 3)]


def test_each_token_is_owned_by_one_window_split_at_the_middle_of_overlaps() -> None:
    windows = plan_windows(10, 4, 2)

    owned = ownership(windows, 10)

    assert owned == [(0, 3), (3, 5), (5, 7), (7, 10)]
    assert all(
        start <= low and high <= end
        for (start, end), (low, high) in zip(windows, owned, strict=True)
    )


def test_token_range_maps_character_spans_to_tokens() -> None:
    starts, ends = [0, 4, 8], [3, 7, 11]  # "abc def ghi"

    assert token_range(starts, ends, (4, 7)) == (1, 2)
    assert token_range(starts, ends, (0, 11)) == (0, 3)
    assert token_range(starts, ends, (5, 9)) == (1, 3)


def test_pool_late_takes_each_token_from_the_window_that_owns_it() -> None:
    runs: list[tuple[int, int]] = []

    def token_vectors(ids: list[int]) -> NDArray[np.float32]:
        """Each token's vector is [its position, the start of the window it was seen in]."""
        runs.append((ids[0], ids[-1] + 1))
        return np.array([[i, ids[0]] for i in ids], dtype=np.float32)

    # Windows (0,4) (2,6) (4,8) (6,10) own tokens (0,3) (3,5) (5,7) (7,10).
    means = pool_late(list(range(10)), [(0, 3), (2, 5), (8, 10)], token_vectors, 2, 4, 2)

    assert means[0].tolist() == [1.0, 0.0]
    assert means[1].tolist() == pytest.approx([3.0, 4 / 3])  # token 2 from window 0, 3-4 from 1
    assert means[2].tolist() == [8.5, 6.0]
    assert runs == [(0, 4), (2, 6), (6, 10)]  # nothing needs window (4, 8)


@pytest.mark.integration
def test_late_vectors_differ_from_naive_ones_for_the_same_chunks() -> None:
    from copilot.ingest.late_chunking import JinaEmbedder

    text = "Acme Corp makes industrial pumps.\n\nIts revenue grew 5% this year."
    spans = [(0, 33), (35, len(text))]
    model = JinaEmbedder()

    late = model.embed_late(text, spans)
    naive = model.embed_documents([text[start:end] for start, end in spans])

    assert late.shape == naive.shape == (2, 512)
    assert np.allclose(np.linalg.norm(late, axis=1), 1.0, atol=1e-5)
    assert not np.allclose(late, naive, atol=1e-3)
