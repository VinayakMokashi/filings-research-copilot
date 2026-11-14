"""The search page's backend (step 9.4, ADR-0038): two rankings of filing passages,
interleaved, and the clicks each earns.

- **The rankings:** `a` is the dense search the doc agent's first stage runs (ADR-0011);
  `b` is hybrid search, the dense ranking fused with BM25's. Both search the filings that
  the query's companies and years pick out, as the doc agent does, and call no model.
- **What is kept:** for each search, the teams in list order, how many filings were
  searched, and how far the two rankings overlapped; for each click, its position and its
  team. Not the query: counting which ranking readers preferred needs no reader's words.
- **Searches in memory.** The newest are held so that a click can find its team, since one
  API instance runs (ADR-0031). A click on a search no longer held is refused, and a
  result clicked twice counts once.
"""

from __future__ import annotations

import random
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from copilot.answer.context import describe
from copilot.retrieval.interleaving import team_draft
from copilot.retrieval.query import CompanyMatcher, Filing, resolve, understand
from copilot.retrieval.search import Hit, Mode

RANKERS: dict[str, Mode] = {"a": "dense", "b": "hybrid"}
RESULTS = 8
SNIPPET = 500  # characters of a passage the list shows; the page opens in full
HELD = 256


class Ranker(Protocol):
    def search(
        self, query: str, mode: Mode = ..., limit: int = ..., doc_names: Sequence[str] | None = ...
    ) -> list[Hit]: ...


class SearchLog(Protocol):
    def start(self, search_id: str, record: dict[str, Any]) -> None: ...
    def click(self, search_id: str, position: int, team: str) -> None: ...


class MemorySearchLog:
    """Searches and clicks kept in the process, for tests and for an API on one machine."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, search_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self.records[search_id] = dict(record) | {"clicks": {}}

    def click(self, search_id: str, position: int, team: str) -> None:
        with self._lock:
            self.records[search_id]["clicks"][position] = team


class InterleavedSearch:
    """Interleaves the two rankings for each search, and credits clicks; see the module
    docstring."""

    def __init__(
        self,
        ranker: Ranker,
        matcher: CompanyMatcher,
        filings: Sequence[Filing],
        log: SearchLog,
        *,
        results: int = RESULTS,
        seed: int | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.ranker = ranker
        self.matcher = matcher
        self.filings = list(filings)
        self.by_name: Mapping[str, Filing] = {filing.doc_name: filing for filing in filings}
        self.log = log
        self.results = results
        self._now = now
        self._rng = random.Random(seed)
        self._held: OrderedDict[str, list[str]] = OrderedDict()
        self._clicked: set[tuple[str, int]] = set()
        self._lock = threading.Lock()

    def search(self, query: str) -> dict[str, Any]:
        """The interleaved results for `query`, with the search's id for its clicks."""
        documents = resolve(understand(query, self.matcher), self.filings)
        a = self.ranker.search(query, RANKERS["a"], self.results, documents)
        b = self.ranker.search(query, RANKERS["b"], self.results, documents)
        with self._lock:
            placed = team_draft(a, b, self.results, self._rng)
            search_id = uuid.uuid4().hex[:16]
            teams = [entry.team for entry in placed]
            self._held[search_id] = teams
            while len(self._held) > HELD:
                gone, _ = self._held.popitem(last=False)
                self._clicked = {claim for claim in self._clicked if claim[0] != gone}
        self.log.start(
            search_id,
            {
                "created": self._now(),
                "teams": teams,
                "filings": len(documents) if documents is not None else None,
                "overlap": len({hit.point_id for hit in a} & {hit.point_id for hit in b}),
            },
        )
        return {
            "search_id": search_id,
            "filings": documents,
            "results": [
                {
                    "position": position,
                    "label": describe(entry.hit.doc_name, entry.hit.pages[0], self.by_name),
                    "doc_name": entry.hit.doc_name,
                    "page": entry.hit.pages[0],
                    "section": entry.hit.section,
                    "text": entry.hit.text[:SNIPPET],
                }
                for position, entry in enumerate(placed)
            ],
        }

    def click(self, search_id: str, position: int) -> bool:
        """Credit a click on a held search's result to its team; False when the search
        isn't held or has no such result. A result clicked again counts once."""
        with self._lock:
            teams = self._held.get(search_id)
            if teams is None or not 0 <= position < len(teams):
                return False
            if (search_id, position) in self._clicked:
                return True
            self._clicked.add((search_id, position))
            team = teams[position]
        self.log.click(search_id, position, team)
        return True
