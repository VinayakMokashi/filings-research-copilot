"""What the API serves from: the copilot, the stores for ratings and preferences, the
exchanges it served (step 9.2), the answer bandit when it is on (step 9.3), the parsed
filing pages and the readiness checks, built once when the application starts.

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
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Protocol

import httpx
import psycopg
from psycopg.types.json import Jsonb

from copilot.agents.build import build_components, postgres_checkpointer, postgres_store
from copilot.agents.graph import Turn
from copilot.agents.router import Route
from copilot.agents.runner import Copilot, Fanout, TraceWriter
from copilot.agents.tracing import build_tracer
from copilot.answer.agent import DocAgent
from copilot.answer.bandit import ArmStats, MemoryArmStats, OnlineChooser
from copilot.answer.context import describe
from copilot.api.bandit import BanditLog, MemoryBanditLog, OnlineBandit
from copilot.api.cache import AnswerCache, MemoryCache, PostgresCache
from copilot.api.exchanges import ExchangeLog
from copilot.api.firestore import (
    Firestore,
    FirestoreArmStats,
    FirestoreBanditLog,
    FirestoreCache,
    FirestoreFeedback,
    FirestorePreferences,
    FirestoreQuotas,
    FirestoreSearchLog,
    FirestoreSpend,
    firestore_client,
)
from copilot.api.quotas import MemoryQuotas, PostgresQuotas, QuotaStore
from copilot.api.search import InterleavedSearch, MemorySearchLog, SearchLog
from copilot.config import Settings
from copilot.ingest.corpus import filing_pages
from copilot.ingest.pdf import Page
from copilot.llm import LLMGateway
from copilot.llm.fallback import MemorySpend, SpendingClient, SpendStore
from copilot.llm.gateway import api_key_for, paid_settings
from copilot.llm.pacing import PacedLLM
from copilot.retrieval.query import Filing
from copilot.sql.agent import facts_db_path


class Asker(Protocol):
    """What the API needs from the copilot: its events for one question."""

    def stream(
        self,
        question: str,
        *,
        thread_id: str,
        user_id: str = "default",
        route: Route | None = None,
        avoid_arm: str | None = None,
    ) -> Iterator[dict[str, Any]]: ...

    def record(self, thread_id: str, turn: Turn) -> None: ...

    def details(self, thread_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Feedback:
    thread_id: str
    turn: int | None
    rating: str
    comment: str
    request_id: str | None


@dataclass(frozen=True, slots=True)
class Preference:
    """A visitor's pick between two answers to one question: `first`, `second` or
    `neither`, with both exchanges (step 9.2)."""

    chosen: str
    comment: str
    first: dict[str, Any]
    second: dict[str, Any]


class FeedbackStore(Protocol):
    def add(self, feedback: Feedback, exchange: dict[str, Any] | None = None) -> int: ...


class PreferenceStore(Protocol):
    def add(self, preference: Preference) -> int: ...


class MemoryFeedback:
    """Feedback kept in the process, for tests and for runs without Postgres."""

    def __init__(self) -> None:
        self.records: list[tuple[datetime, Feedback, dict[str, Any] | None]] = []
        self._lock = threading.Lock()

    def add(self, feedback: Feedback, exchange: dict[str, Any] | None = None) -> int:
        with self._lock:
            self.records.append((datetime.now(UTC), feedback, exchange))
            return len(self.records)


class MemoryPreferences:
    """Preferences kept in the process, for tests and for runs without Postgres."""

    def __init__(self) -> None:
        self.records: list[tuple[datetime, Preference]] = []
        self._lock = threading.Lock()

    def add(self, preference: Preference) -> int:
        with self._lock:
            self.records.append((datetime.now(UTC), preference))
            return len(self.records)


class PostgresFeedback:
    """Feedback in a Postgres table, each rating with the exchange it rates (ADR-0035)."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS feedback (
            id BIGSERIAL PRIMARY KEY,
            created TIMESTAMPTZ NOT NULL DEFAULT now(),
            thread_id TEXT NOT NULL,
            turn INTEGER,
            rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
            comment TEXT NOT NULL DEFAULT '',
            request_id TEXT
        );
        ALTER TABLE feedback ADD COLUMN IF NOT EXISTS exchange JSONB
    """

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self.connection = connection
        self._lock = threading.Lock()
        with self._lock:
            self.connection.execute(self.SCHEMA)

    def add(self, feedback: Feedback, exchange: dict[str, Any] | None = None) -> int:
        with self._lock:
            row = self.connection.execute(
                "INSERT INTO feedback (thread_id, turn, rating, comment, request_id, exchange) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    feedback.thread_id,
                    feedback.turn,
                    feedback.rating,
                    feedback.comment,
                    feedback.request_id,
                    Jsonb(exchange) if exchange is not None else None,
                ),
            ).fetchone()
        return int(row[0]) if row else 0


class PostgresPreferences:
    """Preferences in a Postgres table, with both exchanges."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS preferences (
            id BIGSERIAL PRIMARY KEY,
            created TIMESTAMPTZ NOT NULL DEFAULT now(),
            chosen TEXT NOT NULL CHECK (chosen IN ('first', 'second', 'neither')),
            comment TEXT NOT NULL DEFAULT '',
            first JSONB NOT NULL,
            second JSONB NOT NULL
        )
    """

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self.connection = connection
        self._lock = threading.Lock()
        with self._lock:
            self.connection.execute(self.SCHEMA)

    def add(self, preference: Preference) -> int:
        with self._lock:
            row = self.connection.execute(
                "INSERT INTO preferences (chosen, comment, first, second) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (
                    preference.chosen,
                    preference.comment,
                    Jsonb(preference.first),
                    Jsonb(preference.second),
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
    quotas: QuotaStore = field(default_factory=MemoryQuotas)
    per_visitor: int = 20  # questions a day
    total: int = 200
    cache: AnswerCache | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    exchanges: ExchangeLog = field(default_factory=ExchangeLog)
    preferences: PreferenceStore = field(default_factory=MemoryPreferences)
    bandit: OnlineBandit | None = None
    search: InterleavedSearch | None = None

    def page(self, doc_name: str, page: int) -> tuple[Page, str] | None:
        """A parsed page and its label, or None when there is no such page."""
        pages = filing_pages(self.pages_dir, doc_name)
        if pages is None or page >= len(pages):
            return None
        return pages[page], describe(doc_name, page, self.filings)


def readiness(settings: Settings) -> dict[str, bool]:
    """Whether what the copilot needs is there; never reports a key's value.

    Qdrant is asked for the collection itself, with the key: a real read, which also
    keeps Qdrant Cloud's free cluster from being suspended when the scheduler calls this
    every week (ADR-0031).
    """
    checks = {
        "facts_database": facts_db_path(settings).is_file(),
        "pages": (settings.data_dir / "processed" / "pages").is_dir(),
        "llm_key": settings.groq_api_key is not None,
    }
    if settings.llm_paid_daily_usd or settings.bandit_daily_usd:
        checks["paid_llm_key"] = api_key_for(settings.llm_paid_strong_model, settings) is not None
    key = settings.qdrant_api_key
    headers = {"api-key": key.get_secret_value()} if key is not None else {}
    try:
        checks["qdrant"] = httpx.get(
            f"{settings.qdrant_url}/collections/{settings.collection}",
            headers=headers,
            timeout=5.0,
        ).is_success
    except httpx.HTTPError:
        checks["qdrant"] = False
    if settings.api_state == "firestore":
        try:
            firestore_client().collection("quotas").document("ready").get()
            checks["firestore"] = True
        except Exception:  # any failure means not ready
            checks["firestore"] = False
    if settings.api_state == "postgres":
        try:
            with psycopg.connect(settings.database_url, connect_timeout=2):
                checks["postgres"] = True
        except psycopg.Error:
            checks["postgres"] = False
    return checks


def online_bandit(settings: Settings, client: Firestore | None) -> OnlineBandit | None:
    """The answer bandit when its daily cap is above 0 (ADR-0036): its arms and its judge on
    the paid models, every call counted in the day's `bandit_usd`, its state in Firestore
    when the API keeps its state there, and in memory otherwise."""
    if settings.bandit_daily_usd <= 0:
        return None
    stats: ArmStats
    spend: SpendStore
    log: BanditLog
    if client is not None:
        stats, spend = FirestoreArmStats(client), FirestoreSpend(client, "bandit_usd")
        log = FirestoreBanditLog(client)
    else:
        stats, spend, log = MemoryArmStats(), MemorySpend(), MemoryBanditLog()
    paid = LLMGateway(paid_settings(settings))

    def counted(label: str) -> PacedLLM:  # counts tokens for the run's usage events
        return PacedLLM(SpendingClient(paid, spend, label), pause_s=0.0, attempts=1)

    chooser = OnlineChooser(
        stats,
        spend,
        settings.bandit_daily_usd,
        counted("bandit.arm"),
        control_share=settings.bandit_control_share,
        epsilon0=settings.bandit_epsilon0,
        tau=settings.bandit_tau,
    )
    return OnlineBandit(
        chooser, counted("bandit.judge"), log, judge_share=settings.bandit_judge_share
    )


@contextmanager
def build_services(settings: Settings) -> Iterator[Services]:
    """The real services from settings, open for as long as the application runs."""
    with ExitStack() as stack:
        spend: SpendStore | None = None
        client: Firestore | None = None
        if settings.api_state == "postgres":
            checkpointer = stack.enter_context(postgres_checkpointer(settings))
            store = stack.enter_context(postgres_store(settings))
            connection = stack.enter_context(
                psycopg.connect(settings.database_url, autocommit=True)
            )
            feedback: FeedbackStore = PostgresFeedback(connection)
            preferences: PreferenceStore = PostgresPreferences(connection)
            quotas: QuotaStore = PostgresQuotas(connection)
        elif settings.api_state == "firestore":
            client = firestore_client()
            checkpointer, store = None, None
            feedback = FirestoreFeedback(client)
            preferences = FirestorePreferences(client)
            quotas = FirestoreQuotas(client)
            spend = FirestoreSpend(client) if settings.llm_paid_daily_usd else None
        else:
            checkpointer, store, feedback = None, None, MemoryFeedback()
            preferences = MemoryPreferences()
            quotas = MemoryQuotas()
        cache: AnswerCache | None = None
        if settings.api_cache_days > 0:
            ttl = timedelta(days=settings.api_cache_days)
            if settings.api_state == "postgres":
                cache = PostgresCache(connection, ttl)
            elif client is not None:  # Firestore
                cache = FirestoreCache(client, ttl)
            else:
                cache = MemoryCache(ttl)
        bandit = online_bandit(settings, client)
        arms = bandit.chooser if bandit is not None else None
        parts = build_components(settings, store=store, spend=spend, arms=arms)
        tracer = build_tracer(settings)
        if tracer is not None:
            stack.callback(tracer.close)
        writer = TraceWriter(settings.data_dir / "traces" / "api.jsonl")
        trace = Fanout(writer if settings.api_trace_file else None, tracer)
        doc = getattr(parts.doc, "by_name", {})
        search = None
        if isinstance(parts.doc, DocAgent):
            log: SearchLog = FirestoreSearchLog(client) if client is not None else MemorySearchLog()
            search = InterleavedSearch(
                parts.doc.searcher, parts.doc.matcher, parts.doc.filings, log
            )
        yield Services(
            copilot=Copilot(parts, checkpointer, trace),
            feedback=feedback,
            pages_dir=settings.data_dir / "processed" / "pages",
            checks=partial(readiness, settings),
            filings=doc,
            quotas=quotas,
            per_visitor=settings.api_daily_questions,
            total=settings.api_daily_total,
            cache=cache,
            preferences=preferences,
            bandit=bandit,
            search=search,
        )
