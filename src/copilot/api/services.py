"""What the API serves from: the copilot, a feedback store, the parsed filing pages and the
readiness checks, built once when the application starts.

One copilot run happens at a time in a process. The agents' clients count tokens per
client, and each node's usage is the change in those counts while it runs, so two runs at
once would count each other's tokens; their disk caches are shared files too. The free
tier couldn't serve parallel runs anyway; Phase 8 scales by running more instances.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Protocol

import httpx
import psycopg

from copilot.agents.build import build_components, postgres_checkpointer, postgres_store
from copilot.agents.runner import Copilot, TraceWriter
from copilot.answer.context import describe
from copilot.config import Settings
from copilot.ingest.corpus import pages_path
from copilot.ingest.pdf import Page, read_pages
from copilot.retrieval.query import Filing
from copilot.sql.agent import facts_db_path


class Asker(Protocol):
    """What the API needs from the copilot: its events for one question."""

    def stream(
        self, question: str, *, thread_id: str, user_id: str = "default"
    ) -> Iterator[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class Feedback:
    thread_id: str
    turn: int | None
    rating: str
    comment: str
    request_id: str | None


class FeedbackStore(Protocol):
    def add(self, feedback: Feedback) -> int: ...


class MemoryFeedback:
    """Feedback kept in the process, for tests and for runs without Postgres."""

    def __init__(self) -> None:
        self.records: list[tuple[datetime, Feedback]] = []
        self._lock = threading.Lock()

    def add(self, feedback: Feedback) -> int:
        with self._lock:
            self.records.append((datetime.now(UTC), feedback))
            return len(self.records)


class PostgresFeedback:
    """Feedback in a Postgres table, kept for Phase 9's preference pairs."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS feedback (
            id BIGSERIAL PRIMARY KEY,
            created TIMESTAMPTZ NOT NULL DEFAULT now(),
            thread_id TEXT NOT NULL,
            turn INTEGER,
            rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
            comment TEXT NOT NULL DEFAULT '',
            request_id TEXT
        )
    """

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self.connection = connection
        self._lock = threading.Lock()
        with self._lock:
            self.connection.execute(self.SCHEMA)

    def add(self, feedback: Feedback) -> int:
        with self._lock:
            row = self.connection.execute(
                "INSERT INTO feedback (thread_id, turn, rating, comment, request_id) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (
                    feedback.thread_id,
                    feedback.turn,
                    feedback.rating,
                    feedback.comment,
                    feedback.request_id,
                ),
            ).fetchone()
        return int(row[0]) if row else 0


@dataclass
class Services:
    """Everything a request may use; `lock` lets one copilot run happen at a time."""

    copilot: Asker
    feedback: FeedbackStore
    pages_dir: Path
    checks: Callable[[], dict[str, bool]]
    filings: Mapping[str, Filing] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def page(self, doc_name: str, page: int) -> tuple[Page, str] | None:
        """A parsed page and its label, or None when there is no such page."""
        path = pages_path(self.pages_dir, doc_name)
        if not path.is_file():
            return None
        pages = _pages(path, path.stat().st_mtime_ns)
        if page >= len(pages):
            return None
        return pages[page], describe(doc_name, page, self.filings)


@lru_cache(maxsize=16)
def _pages(path: Path, _mtime: int) -> list[Page]:
    """A filing's pages, read once while the file is unchanged."""
    return read_pages(path)


def readiness(settings: Settings) -> dict[str, bool]:
    """Whether what the copilot needs is there; never reports a key's value."""
    checks = {
        "facts_database": facts_db_path(settings).is_file(),
        "pages": (settings.data_dir / "processed" / "pages").is_dir(),
        "llm_key": settings.groq_api_key is not None,
    }
    try:
        checks["qdrant"] = httpx.get(f"{settings.qdrant_url}/readyz", timeout=2.0).is_success
    except httpx.HTTPError:
        checks["qdrant"] = False
    if settings.api_state == "postgres":
        try:
            with psycopg.connect(settings.database_url, connect_timeout=2):
                checks["postgres"] = True
        except psycopg.Error:
            checks["postgres"] = False
    return checks


@contextmanager
def build_services(settings: Settings) -> Iterator[Services]:
    """The real services from settings, open for as long as the application runs."""
    with ExitStack() as stack:
        if settings.api_state == "postgres":
            checkpointer = stack.enter_context(postgres_checkpointer(settings))
            store = stack.enter_context(postgres_store(settings))
            connection = stack.enter_context(
                psycopg.connect(settings.database_url, autocommit=True)
            )
            feedback: FeedbackStore = PostgresFeedback(connection)
        else:
            checkpointer, store, feedback = None, None, MemoryFeedback()
        parts = build_components(settings, store=store)
        trace = TraceWriter(settings.data_dir / "traces" / "api.jsonl")
        doc = getattr(parts.doc, "by_name", {})
        yield Services(
            copilot=Copilot(parts, checkpointer, trace),
            feedback=feedback,
            pages_dir=settings.data_dir / "processed" / "pages",
            checks=partial(readiness, settings),
            filings=doc,
        )
