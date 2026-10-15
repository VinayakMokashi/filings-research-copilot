"""Shared fixtures: isolated configuration and no network access."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from pydantic import SecretStr

from copilot.config import Settings

_PROJECT_PREFIX = "FRC_"
# Settings read under their own names (GROQ_API_KEY, SEC_USER_AGENT, ...), taken from the
# model so that a newly added aliased setting is isolated too.
_THIRD_PARTY = frozenset(
    field.validation_alias
    for field in Settings.model_fields.values()
    if isinstance(field.validation_alias, str)
)
_LOCAL_HOSTS = frozenset({"", "localhost", "127.0.0.1", "::1"})


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hide the developer's real configuration and logging setup from every test."""
    for name in list(os.environ):
        if name.startswith(_PROJECT_PREFIX) or name in _THIRD_PARTY:
            monkeypatch.delenv(name, raising=False)
    yield
    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse DNS lookups of non-local hosts, so a call without `mock_response` can't go out."""
    real_getaddrinfo = socket.getaddrinfo

    def local_only(host: Any, *args: Any, **kwargs: Any) -> Any:
        name = host.decode() if isinstance(host, bytes) else host
        if name is not None and name not in _LOCAL_HOSTS:
            raise OSError(f"Unit tests must not use the network (DNS lookup of {name!r}).")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_only)


@pytest.fixture
def settings() -> Settings:
    """Settings with a dummy Groq key; never reads a `.env` file."""
    return Settings(_env_file=None, groq_api_key=SecretStr("test-groq-key"))
