"""The demo database's helpers: the gcloud command lines, waiting for a state, the
reader's URL. Nothing here calls gcloud."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from copilot.deploy import gcloud
from copilot.deploy.cloudsql import (
    GRANTS,
    import_sql,
    new_password,
    reader_url,
    set_activation,
    wait_for,
)


def test_commands_name_the_copilots_project() -> None:
    up = set_activation("ALWAYS")

    assert up[1:] == [
        "sql", "instances", "patch", "facts", "--activation-policy=ALWAYS", "--quiet",
        "--project=filings-research-copilot",
    ]  # fmt: skip
    assert "--user=postgres" in import_sql("gs://bucket/facts.sql.gz")


def test_gcloud_runs_with_the_copilots_own_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    class Result:
        stdout = "RUNNABLE\n"

    def fake_run(args: list[str], **kwargs: object) -> Result:
        env = kwargs["env"]
        assert isinstance(env, dict)
        seen["config"] = env["CLOUDSDK_ACTIVE_CONFIG_NAME"]
        return Result()

    monkeypatch.setattr("copilot.deploy.gcloud.subprocess.run", fake_run)

    assert gcloud.run(["gcloud", "version"], capture=True) == "RUNNABLE"
    assert seen == {"config": "frc"}


def test_waiting_returns_the_state_it_waited_for() -> None:
    states = iter(["PENDING_CREATE", "PENDING_CREATE", "RUNNABLE"])
    naps: list[float] = []

    state = wait_for(lambda: next(states), lambda s: s == "RUNNABLE", sleep=naps.append)

    assert state == "RUNNABLE"
    assert naps == [10.0, 10.0]


def test_waiting_gives_up_at_the_deadline() -> None:
    now = [0.0]

    def nap(seconds: float) -> None:
        now[0] += seconds

    with pytest.raises(TimeoutError, match="STOPPED"):
        wait_for(
            lambda: "STOPPED",
            lambda s: s == "RUNNABLE",
            timeout_s=30,
            sleep=nap,
            clock=lambda: now[0],
        )


def test_the_readers_url_requires_tls_and_escapes_its_password() -> None:
    url = reader_url("10.20.0.3", "a/b+c@d")
    parts = urlsplit(url)

    assert parts.hostname == "10.20.0.3"
    assert parts.username == "facts_reader"
    assert parts.password == "a%2Fb%2Bc%40d"
    assert parts.path == "/facts"
    assert "sslmode=require" in parts.query
    assert "connect_timeout=2" in parts.query
    assert len(new_password()) >= 32


def test_the_reader_may_only_read() -> None:
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO facts_reader" in GRANTS
    assert "default_transaction_read_only = on" in GRANTS
    assert "INSERT" not in GRANTS
    assert "UPDATE" not in GRANTS
