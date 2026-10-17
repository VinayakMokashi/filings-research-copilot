"""Cross-encoder reranking (step 2.4).

Search embeds the query and each passage separately, which is what makes it fast enough
for a whole corpus, but the two texts never meet inside the model. A cross-encoder reads
the query and one passage together and scores how well they match. That is more precise
and costs one model run per passage, so it only reorders the top few dozen candidates.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from copilot.retrieval.search import Hit

RERANKERS = {
    "minilm-l6": "Xenova/ms-marco-MiniLM-L-6-v2",
    "minilm-l12": "Xenova/ms-marco-MiniLM-L-12-v2",
    "jina-turbo": "jinaai/jina-reranker-v1-turbo-en",
    "bge-base": "BAAI/bge-reranker-base",
}


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class FastEmbedReranker:
    """A FastEmbed cross-encoder; downloaded on first use and cached in `cache_dir`."""

    def __init__(self, key: str, *, cache_dir: Path | None = None, batch_size: int = 1) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.key = key
        self.model_id = RERANKERS[key]
        self._batch_size = batch_size
        self._model: Any = TextCrossEncoder(
            self.model_id, cache_dir=str(cache_dir) if cache_dir else None
        )

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        scores = self._model.rerank(query, list(texts), batch_size=self._batch_size)
        return [float(value) for value in scores]


_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class OverlapReranker:
    """Scores by the number of distinct query words in the passage; a stand-in for tests."""

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        words = set(_WORD.findall(query.lower()))
        return [float(len(words & set(_WORD.findall(text.lower())))) for text in texts]


def rerank(reranker: Reranker, query: str, hits: Sequence[Hit], top: int) -> list[Hit]:
    """The first `top` hits reordered by the reranker's scores, then the rest unchanged."""
    head, tail = list(hits[:top]), list(hits[top:])
    scores = reranker.score(query, [hit.text for hit in head])
    order = sorted(range(len(head)), key=lambda i: -scores[i])
    return [replace(head[i], score=scores[i]) for i in order] + tail
