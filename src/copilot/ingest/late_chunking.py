"""Late chunking: embed long stretches of the document, then pool token vectors per chunk.

A chunk embedded on its own sees only its own words, so "the Company", "this segment" or a
table's column headers on the previous page lose their referent. Late chunking (Günther et
al., 2024) runs a long-context model over a window of the document, so every token's vector
is conditioned on its neighbourhood, and only then averages the token vectors inside each
chunk. The chunks themselves are unchanged; only their vectors differ.

The model is jinaai/jina-embeddings-v2-small-en (512 dimensions, ALiBi attention, trained
for up to 8,192 tokens), run through ONNX Runtime for its token-level output. Windows are
2,048 tokens, because attention cost grows with the square of the length (1,600 tokens per
second at 2,048 against 5,000 at 512 on the build laptop). Neighbouring windows overlap by
512 tokens, and each token takes its vector from the window it sits nearer the middle of,
so every token has at least 256 tokens of context on both sides (except at the document's
ends), and a chunk can straddle two windows.

`JinaEmbedder.embed_documents` is the naive baseline with the same weights: each chunk
embedded on its own and mean-pooled over all its tokens, as the model was trained.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray

from copilot.ingest.embed import normalise

JINA_REPO = "jinaai/jina-embeddings-v2-small-en"
WINDOW_TOKENS = 2048
WINDOW_OVERLAP = 512

# Token vectors, in context, for a window of token ids (without [CLS] and [SEP]).
TokenVectors = Callable[[list[int]], NDArray[np.float32]]


def plan_windows(tokens: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Token windows [start, end) of up to `size`, each starting `size - overlap` after the last."""
    if tokens <= size:
        return [(0, tokens)]
    windows = []
    start = 0
    while True:
        end = min(start + size, tokens)
        windows.append((start, end))
        if end == tokens:
            return windows
        start += size - overlap


def ownership(windows: Sequence[tuple[int, int]], tokens: int) -> list[tuple[int, int]]:
    """The tokens each window supplies: from the middle of one overlap to the middle of the next."""
    middles = [(following[0] + current[1]) // 2 for current, following in pairwise(windows)]
    return list(pairwise([0, *middles, tokens]))


def token_range(
    starts: Sequence[int], ends: Sequence[int], span: tuple[int, int]
) -> tuple[int, int]:
    """Indexes [first, last) of the tokens that overlap the character span [start, end)."""
    first = bisect.bisect_right(ends, span[0])
    last = bisect.bisect_left(starts, span[1])
    return first, max(last, first + 1)


def pool_late(
    ids: Sequence[int],
    ranges: Sequence[tuple[int, int]],
    token_vectors: TokenVectors,
    dim: int,
    size: int = WINDOW_TOKENS - 2,
    overlap: int = WINDOW_OVERLAP,
) -> NDArray[np.float32]:
    """The mean in-context token vector of each token range; windows nobody needs are skipped."""
    windows = plan_windows(len(ids), size, overlap)
    sums = np.zeros((len(ranges), dim), dtype=np.float64)
    counts = np.zeros(len(ranges), dtype=np.float64)
    for (start, end), (own_start, own_end) in zip(
        windows, ownership(windows, len(ids)), strict=True
    ):
        wanted = [
            i for i, (first, last) in enumerate(ranges) if first < own_end and last > own_start
        ]
        if not wanted:
            continue
        vectors = token_vectors(list(ids[start:end]))
        for i in wanted:
            low, high = max(ranges[i][0], own_start), min(ranges[i][1], own_end)
            sums[i] += vectors[low - start : high - start].sum(axis=0)
            counts[i] += high - low
    means: NDArray[np.float32] = (sums / np.maximum(counts, 1.0)[:, None]).astype(np.float32)
    return means


class JinaEmbedder:
    """jina-embeddings-v2-small-en through ONNX Runtime, chunk by chunk or late-chunked."""

    key = "jina-small"
    dim = 512

    def __init__(
        self,
        *,
        window: int = WINDOW_TOKENS,
        overlap: int = WINDOW_OVERLAP,
        threads: int | None = None,
    ) -> None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        if threads:
            options.intra_op_num_threads = threads
        self._session: Any = ort.InferenceSession(
            hf_hub_download(JINA_REPO, "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer: Any = Tokenizer.from_file(hf_hub_download(JINA_REPO, "tokenizer.json"))
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        cls, sep = self._tokenizer.token_to_id("[CLS]"), self._tokenizer.token_to_id("[SEP]")
        if cls is None or sep is None:
            raise ValueError("The jina tokenizer has no [CLS] or [SEP] token.")
        self._cls: int = cls
        self._sep: int = sep
        self._size = window - 2  # room for [CLS] and [SEP]
        self._overlap = overlap

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        """Each text on its own (naive chunking), mean-pooled over all its tokens."""
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            ids = self._tokenizer.encode(text, add_special_tokens=False).ids[: self._size]
            vectors[row] = self._run([self._cls, *ids, self._sep]).mean(axis=0)
        return normalise(vectors)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        vector: NDArray[np.float32] = self.embed_documents([text])[0]
        return vector

    def embed_late(self, text: str, spans: Sequence[tuple[int, int]]) -> NDArray[np.float32]:
        """One vector per character span of `text`, pooled from in-context token vectors."""
        encoding = self._tokenizer.encode(text, add_special_tokens=False)
        starts = [start for start, _ in encoding.offsets]
        ends = [end for _, end in encoding.offsets]
        ranges = [token_range(starts, ends, span) for span in spans]
        means = pool_late(
            encoding.ids, ranges, self._token_vectors, self.dim, self._size, self._overlap
        )
        return normalise(means)

    def _token_vectors(self, ids: list[int]) -> NDArray[np.float32]:
        return self._run([self._cls, *ids, self._sep])[1:-1]

    def _run(self, ids: list[int]) -> NDArray[np.float32]:
        batch = np.array([ids], dtype=np.int64)
        feed = {
            "input_ids": batch,
            "attention_mask": np.ones_like(batch),
            "token_type_ids": np.zeros_like(batch),
        }
        output: NDArray[np.float32] = self._session.run(None, feed)[0][0]
        return output
