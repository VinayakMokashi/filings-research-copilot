"""Daily question quotas: counting, limits, the reset time and visitor ids."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from starlette.requests import Request

from copilot.api.quotas import MemoryQuotas, PostgresQuotas, seconds_until_reset, visitor_key
from copilot.config import get_settings

DAY = date(2026, 10, 26)


def request(headers: dict[str, str], host: str = "203.0.113.7") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": (host, 50000)})


def test_memory_quotas_count_per_visitor_per_day() -> None:
    quotas = MemoryQuotas()

    assert [quotas.take("a", DAY, 2, 10).allowed for _ in range(3)] == [True, True, False]
    assert quotas.take("a", DAY, 2, 10).over == "visitor"
    assert quotas.take("a", date(2026, 10, 27), 2, 10).allowed  # a new day
    assert quotas.take("b", DAY, 2, 3).allowed
    assert quotas.take("c", DAY, 2, 3).over == "total"  # a, a and b on DAY already


def test_quotas_reset_at_midnight_utc() -> None:
    assert seconds_until_reset(datetime(2026, 10, 26, 23, 59, 30, tzinfo=UTC)) == 30
    assert seconds_until_reset(datetime(2026, 10, 26, 0, 0, 0, tzinfo=UTC)) == 86_400


def test_visitors_are_hashed_and_a_bad_header_falls_back_to_the_address() -> None:
    by_header = visitor_key(request({"X-Visitor-ID": "visitor-0001"}))

    assert by_header == visitor_key(request({"X-Visitor-ID": "visitor-0001"}, host="198.51.100.1"))
    assert "visitor" not in by_header
    assert len(by_header) == 16
    assert visitor_key(request({"X-Visitor-ID": "short"})) == visitor_key(request({}))


@pytest.mark.integration
def test_postgres_quotas_survive_a_new_connection() -> None:
    psycopg = pytest.importorskip("psycopg")
    settings = get_settings()
    visitor, day = f"test-{uuid.uuid4().hex[:8]}", date(2001, 1, 1)
    try:
        with psycopg.connect(settings.database_url, autocommit=True) as first:
            assert PostgresQuotas(first).take(visitor, day, 1, 1000).allowed
        with psycopg.connect(settings.database_url, autocommit=True) as second:
            assert PostgresQuotas(second).take(visitor, day, 1, 1000).over == "visitor"
    finally:
        with psycopg.connect(settings.database_url, autocommit=True) as cleanup:
            cleanup.execute("DELETE FROM question_quota WHERE visitor = %s", (visitor,))
