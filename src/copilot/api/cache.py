"""Answers to repeated questions, served again without a run (step 6.2).

A question asked again, word for word once case, spacing and quote marks are evened out,
gets the stored answer: no model call, and nothing counted against the quotas. Only
answers that are safe to reuse are kept and served:

- **a new conversation from an anonymous caller,** since a follow-up depends on its
  conversation and a named user's question may be rewritten from their notes;
- **an answer the copilot actually gave,** never a refusal, a decline or a "try again
  later";
- **younger than the time to live** (`FRC_API_CACHE_DAYS`, seven days; 0 turns the cache
  off).

Questions are matched exactly, not by embedding similarity. On the routing set's pairs, a
question with its measure swapped ("operating income" for "revenue") was more similar to
the original than the original's own paraphrases at every threshold that let paraphrases
through, so a similarity cache would serve one measure's answer to another's question
(`poe eval-semantic-cache`, and the semantic cache guide).
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb

_SPACE = re.compile(r"\s+")
_QUOTES = str.maketrans(
    {
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{LEFT DOUBLE QUOTATION MARK}": '"',
        "\N{RIGHT DOUBLE QUOTATION MARK}": '"',
    }
)


def normalise_question(question: str) -> str:
    """The question as the cache matches it: case, spacing, quote marks and ends evened out."""
    text = unicodedata.normalize("NFKC", question).translate(_QUOTES).casefold()
    return _SPACE.sub(" ", text).strip().rstrip("?!. ").strip()


@dataclass(frozen=True, slots=True)
class Cached:
    question: str
    response: dict[str, Any]
    created: datetime


class AnswerCache(Protocol):
    def get(self, question: str, now: datetime) -> Cached | None: ...

    def put(self, question: str, response: dict[str, Any], now: datetime) -> None: ...


def reusable(response: dict[str, Any]) -> bool:
    """Whether a response may be served again: an answer, not a refusal or an error."""
    return bool(response.get("answered")) and not response.get("error")


class MemoryCache:
    """Answers kept in the process, for tests and for runs without Postgres."""

    def __init__(self, ttl: timedelta) -> None:
        self.ttl = ttl
        self.entries: dict[str, Cached] = {}
        self._lock = threading.Lock()

    def get(self, question: str, now: datetime) -> Cached | None:
        with self._lock:
            found = self.entries.get(normalise_question(question))
        return found if found is not None and now - found.created < self.ttl else None

    def put(self, question: str, response: dict[str, Any], now: datetime) -> None:
        with self._lock:
            self.entries[normalise_question(question)] = Cached(question, response, now)


class PostgresCache:
    """Answers in a Postgres table, so a restart keeps them."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS answer_cache (
            key TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            response JSONB NOT NULL,
            created TIMESTAMPTZ NOT NULL
        )
    """

    def __init__(self, connection: psycopg.Connection[Any], ttl: timedelta) -> None:
        self.connection = connection
        self.ttl = ttl
        self._lock = threading.Lock()
        with self._lock:
            self.connection.execute(self.SCHEMA)

    def get(self, question: str, now: datetime) -> Cached | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT question, response, created FROM answer_cache "
                "WHERE key = %s AND created > %s",
                (normalise_question(question), now - self.ttl),
            ).fetchone()
        if row is None:
            return None
        response = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        return Cached(str(row[0]), response, row[2])

    def put(self, question: str, response: dict[str, Any], now: datetime) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO answer_cache (key, question, response, created) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (key) DO UPDATE SET question = EXCLUDED.question, "
                "response = EXCLUDED.response, created = EXCLUDED.created",
                (normalise_question(question), question, Jsonb(response), now),
            )


def age_seconds(cached: Cached, now: datetime) -> int:
    return int((now - cached.created.astimezone(UTC)).total_seconds())
