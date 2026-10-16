"""SEC EDGAR: the company ticker list, company submissions and XBRL company facts.

SEC asks every client to send a User-Agent that names a contact, and to stay under 10
requests per second. `SecClient` enforces both: it refuses to start without a contact
email, spaces requests at least 1/rate seconds apart, and retries 429 and 5xx responses
with backoff, honouring `Retry-After`.

Downloads are cached as raw JSON under `data/raw/sec/`, so a rerun only fetches what is
missing.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict

from copilot.http import make_client
from copilot.logs import get_logger

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

SEC_LIMIT_PER_SECOND = 10.0
DEFAULT_PER_SECOND = 5.0
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

log = get_logger(__name__)


class SecError(RuntimeError):
    """SEC refused or failed a request after every retry."""


class Ticker(BaseModel):
    """One row of SEC's company ticker list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cik_str: int
    ticker: str
    title: str


class SecClient:
    """A polite EDGAR client: declared contact, rate limit and retries."""

    def __init__(
        self,
        user_agent: str | None,
        *,
        per_second: float = DEFAULT_PER_SECOND,
        attempts: int = 4,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent with a contact, such as 'Jane Doe jane@example.com'. "
                "Set SEC_USER_AGENT in .env."
            )
        if not 0 < per_second <= SEC_LIMIT_PER_SECOND:
            raise ValueError(
                f"per_second must be in (0, {SEC_LIMIT_PER_SECOND:g}], got {per_second}."
            )
        self._client = client or make_client(user_agent=user_agent)
        self._client.headers["User-Agent"] = user_agent
        self._interval = 1.0 / per_second
        self._attempts = attempts
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def get(self, url: str) -> bytes:
        """The response body for `url`, after rate limiting and retries."""
        for attempt in range(1, self._attempts + 1):
            self._wait_turn()
            try:
                response = self._client.get(url)
            except httpx.TransportError as exc:
                if attempt == self._attempts:
                    raise SecError(f"GET {url} failed: {exc}") from exc
                self._sleep(2.0 ** (attempt - 1))
                continue
            if response.status_code == httpx.codes.OK:
                return response.content
            if response.status_code not in _RETRY_STATUSES or attempt == self._attempts:
                raise SecError(f"GET {url} returned HTTP {response.status_code}.")
            self._sleep(_retry_delay(response, attempt))
        raise AssertionError("unreachable")

    def get_json(self, url: str) -> Any:
        return json.loads(self.get(url))

    def _wait_turn(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self._interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
                now += remaining
        self._last = now

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return float(retry_after)
    return 2.0 ** (attempt - 1)


@dataclass(frozen=True, slots=True)
class Download:
    """A cached EDGAR file and when it was fetched."""

    path: Path
    url: str
    fetched_at: datetime
    size: int
    sha256: str
    downloaded: bool


def fetch_cached(client: SecClient, url: str, dest: Path, *, refresh: bool = False) -> Download:
    """Fetch `url` into `dest` unless it is already cached; the JSON is checked before saving."""
    if dest.is_file() and not refresh:
        data = dest.read_bytes()
        fetched_at = datetime.fromtimestamp(dest.stat().st_mtime, tz=UTC)
        downloaded = False
    else:
        data = client.get(url)
        json.loads(data)  # refuse to cache anything that isn't JSON
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        partial.write_bytes(data)
        partial.replace(dest)
        fetched_at = datetime.now(UTC)
        downloaded = True
        log.info("sec.downloaded", url=url, size=len(data))
    return Download(
        path=dest,
        url=url,
        fetched_at=fetched_at,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        downloaded=downloaded,
    )


def parse_tickers(payload: dict[str, Any]) -> list[Ticker]:
    """SEC's ticker list, which is keyed "0", "1", ... in the order SEC ranks companies."""
    return [
        Ticker.model_validate(row) for _, row in sorted(payload.items(), key=lambda kv: int(kv[0]))
    ]
