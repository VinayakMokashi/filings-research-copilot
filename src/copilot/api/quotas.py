"""Daily question quotas, per visitor and in total (step 6.2).

The free tier allows each model about 200,000 tokens a day, a few dozen answers, so a
public copilot needs two limits: one per visitor, so that one person can't spend the day's
budget, and one in total, so that many can't either. Both reset at midnight UTC, and a
question over either gets a 429 with `Retry-After` before any model call.

A visitor is whoever sends the same `X-Visitor-ID` header (the UI keeps one per browser
session), or else the same address. The header is the client's word, so a client that
changes it at will escapes its own limit, but not the total. Visitors are stored as a
short hash, never as the id or address itself.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol

import psycopg
from fastapi import Request

_VISITOR = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@dataclass(frozen=True, slots=True)
class Verdict:
    allowed: bool
    over: Literal["visitor", "total"] | None = None


class QuotaStore(Protocol):
    def take(self, visitor: str, day: date, per_visitor: int, total: int) -> Verdict:
        """Count one question for `visitor` on `day`, unless a limit is already reached."""
        ...


class MemoryQuotas:
    """Quotas kept in the process: for tests, and for runs without Postgres."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, date], int] = {}
        self._lock = threading.Lock()

    def take(self, visitor: str, day: date, per_visitor: int, total: int) -> Verdict:
        with self._lock:
            mine = self.counts.get((visitor, day), 0)
            everyone = sum(n for (_, counted), n in self.counts.items() if counted == day)
            if mine >= per_visitor:
                return Verdict(False, "visitor")
            if everyone >= total:
                return Verdict(False, "total")
            self.counts[(visitor, day)] = mine + 1
            return Verdict(True)


class PostgresQuotas:
    """Quotas in a Postgres table, so a restart doesn't hand out a new day's budget."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS question_quota (
            visitor TEXT NOT NULL,
            day DATE NOT NULL,
            questions INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (visitor, day)
        )
    """

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self.connection = connection
        self._lock = threading.Lock()
        with self._lock:
            self.connection.execute(self.SCHEMA)

    def take(self, visitor: str, day: date, per_visitor: int, total: int) -> Verdict:
        with self._lock, self.connection.transaction():
            mine = self.connection.execute(
                "SELECT questions FROM question_quota WHERE visitor = %s AND day = %s",
                (visitor, day),
            ).fetchone()
            everyone = self.connection.execute(
                "SELECT COALESCE(SUM(questions), 0) FROM question_quota WHERE day = %s", (day,)
            ).fetchone()
            if mine is not None and int(mine[0]) >= per_visitor:
                return Verdict(False, "visitor")
            if everyone is not None and int(everyone[0]) >= total:
                return Verdict(False, "total")
            self.connection.execute(
                "INSERT INTO question_quota (visitor, day, questions) VALUES (%s, %s, 1) "
                "ON CONFLICT (visitor, day) DO UPDATE SET questions = question_quota.questions + 1",
                (visitor, day),
            )
            return Verdict(True)


def visitor_key(request: Request) -> str:
    """The visitor's id (a valid `X-Visitor-ID`, else the address), hashed."""
    given = request.headers.get("x-visitor-id", "")
    if not _VISITOR.match(given):
        given = request.client.host if request.client else "unknown"
    return hashlib.sha256(given.encode()).hexdigest()[:16]


def seconds_until_reset(now: datetime) -> int:
    """Seconds until the quotas reset, at the next midnight UTC; at least one."""
    tomorrow = (now.astimezone(UTC) + timedelta(days=1)).date()
    midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))
