"""The SEC EDGAR client: declared contact, rate limit, retries and caching (mocked transport)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from copilot.ingest import sec

AGENT = "Test Person test@example.com"
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000066740.json"


class FakeTime:
    """A clock that only moves when the client sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _client(
    responses: list[httpx.Response], seen: list[httpx.Request] | None = None
) -> tuple[sec.SecClient, FakeTime]:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return queue.pop(0)

    time = FakeTime()
    client = sec.SecClient(
        AGENT,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=time.sleep,
        clock=time.clock,
    )
    return client, time


@pytest.mark.parametrize("agent", [None, "", "filings-research-copilot"])
def test_a_contact_email_is_required(agent: str | None) -> None:
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        sec.SecClient(agent)


def test_the_rate_cannot_exceed_sec_limit() -> None:
    with pytest.raises(ValueError, match="per_second"):
        sec.SecClient(AGENT, per_second=11)


def test_requests_carry_the_declared_contact() -> None:
    seen: list[httpx.Request] = []
    client, _ = _client([httpx.Response(200, json={"ok": True})], seen)

    assert client.get_json(URL) == {"ok": True}
    assert seen[0].headers["User-Agent"] == AGENT


def test_requests_are_spaced_to_the_rate_limit() -> None:
    client, time = _client([httpx.Response(200, json={})] * 3)

    for _ in range(3):
        client.get(URL)

    assert time.sleeps == pytest.approx([0.2, 0.2])  # 5 requests per second by default


def test_server_errors_are_retried_with_backoff() -> None:
    client, time = _client(
        [httpx.Response(503), httpx.Response(503), httpx.Response(200, text="{}")]
    )

    assert client.get(URL) == b"{}"
    assert time.sleeps == pytest.approx([1.0, 2.0])


def test_retry_after_is_honoured() -> None:
    client, time = _client(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, text="{}")]
    )

    client.get(URL)

    assert time.sleeps == [7.0]


def test_client_errors_are_not_retried() -> None:
    client, time = _client([httpx.Response(404)])

    with pytest.raises(sec.SecError, match="404"):
        client.get(URL)
    assert time.sleeps == []


def test_retries_give_up_eventually() -> None:
    client, _ = _client([httpx.Response(500)] * 4)

    with pytest.raises(sec.SecError, match="500"):
        client.get(URL)


def test_fetch_cached_downloads_once(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    client, _ = _client([httpx.Response(200, json={"cik": 66740})], seen)
    dest = tmp_path / "companyfacts" / "CIK0000066740.json"

    first = sec.fetch_cached(client, URL, dest)
    again = sec.fetch_cached(client, URL, dest)

    assert (first.downloaded, again.downloaded) == (True, False)
    assert first.sha256 == again.sha256
    assert json.loads(dest.read_bytes()) == {"cik": 66740}
    assert len(seen) == 1


def test_fetch_cached_refuses_a_non_json_body(tmp_path: Path) -> None:
    client, _ = _client([httpx.Response(200, text="<html>blocked</html>")])
    dest = tmp_path / "x.json"

    with pytest.raises(ValueError, match="Expecting value"):
        sec.fetch_cached(client, URL, dest)
    assert not dest.exists()


def test_parse_tickers_keeps_sec_order() -> None:
    payload = {
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "10": {"cik_str": 66740, "ticker": "MMM", "title": "3M CO"},
    }

    assert [t.ticker for t in sec.parse_tickers(payload)] == ["NVDA", "AAPL", "MMM"]
