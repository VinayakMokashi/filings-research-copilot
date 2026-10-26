"""The answer cache: what counts as the same question, and what may be kept."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from copilot.api.cache import MemoryCache, PostgresCache, normalise_question, reusable
from copilot.config import get_settings

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
REPLY = {"text": "Capex was $1,577 million [1].", "answered": True}


def test_questions_match_once_case_spacing_quotes_and_ends_are_evened_out() -> None:
    plain = normalise_question("What was 3M's capital expenditure in 2018?")

    assert (
        normalise_question(
            "  what was 3M\N{RIGHT SINGLE QUOTATION MARK}s capital   expenditure in 2018 "
        )
        == plain
    )
    assert normalise_question("What was 3M's capital expenditure in 2019?") != plain


def test_only_answers_are_reusable() -> None:
    assert reusable(REPLY)
    assert not reusable({"text": "Please try again later.", "answered": False})
    assert not reusable(REPLY | {"error": "the run failed"})


def test_a_stored_answer_expires() -> None:
    cache = MemoryCache(timedelta(days=7))
    cache.put("What was 3M's capex?", REPLY, NOW)

    assert cache.get("what was 3m's capex", NOW + timedelta(days=6)) is not None
    assert cache.get("What was 3M's capex?", NOW + timedelta(days=7)) is None


@pytest.mark.integration
def test_postgres_keeps_answers_across_connections() -> None:
    psycopg = pytest.importorskip("psycopg")
    settings = get_settings()
    question = f"Test question {uuid.uuid4().hex[:8]}?"
    try:
        with psycopg.connect(settings.database_url, autocommit=True) as first:
            PostgresCache(first, timedelta(days=7)).put(question, REPLY, NOW)
        with psycopg.connect(settings.database_url, autocommit=True) as second:
            found = PostgresCache(second, timedelta(days=7)).get(question.lower(), NOW)
            assert found is not None
            assert found.response == REPLY
    finally:
        with psycopg.connect(settings.database_url, autocommit=True) as cleanup:
            cleanup.execute(
                "DELETE FROM answer_cache WHERE key = %s", (normalise_question(question),)
            )
