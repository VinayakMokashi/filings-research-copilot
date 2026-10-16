"""One place to configure HTTP clients for the data fetchers."""

from __future__ import annotations

import httpx

from copilot import __version__

PROJECT_USER_AGENT = (
    f"filings-research-copilot/{__version__} "
    "(+https://github.com/VinayakMokashi/filings-research-copilot)"
)


def make_client(*, user_agent: str = PROJECT_USER_AGENT, timeout_s: float = 60.0) -> httpx.Client:
    """An HTTP client that names this project, follows redirects and retries failed connects.

    Retries cover connection errors only; HTTP error statuses are left to the caller.
    """
    return httpx.Client(
        headers={"User-Agent": user_agent},
        timeout=timeout_s,
        follow_redirects=True,
        transport=httpx.HTTPTransport(retries=3),
    )
