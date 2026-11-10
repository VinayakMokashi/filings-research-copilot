"""The demo database's helpers: the gcloud command lines, waiting for an operation, the
reader's URL. Nothing here calls gcloud."""

from __future__ import annotations

import subprocess
import sys
from urllib.parse import urlsplit

import pytest

from copilot.deploy import gcloud
from copilot.deploy.cloudsql import (
    GRANTS,
    change_activation,
    describe_operation,
    import_sql,
    new_password,
    reader_url,
    set_activation,
    wait_for,
)


def test_commands_name_the_copilots_project() -> None:
    up = set_activation("ALWAYS")

    assert up[1:] == [
        "sql", "instances", "patch", "facts", "--activation-policy=ALWAYS", "--async",
        "--quiet", "--format=value(name)", "--project=filings-research-copilot",
    ]  # fmt: skip
    assert describe_operation("op-1")[1:4] == ["sql", "operations", "describe"]
    assert "--user=postgres" in import_sql("gs://bucket/facts.sql.gz")


class FakeCloudSql:
    """Answers the three command lines a window runs, and records which ran."""

    def __init__(self, statuses: list[str]) -> None:
        self.statuses = iter(statuses)
        self.calls: list[str] = []

    def __call__(self, line: list[str]) -> str:
        verb = " ".join(line[1:4])
        self.calls.append(verb)
        if verb == "sql instances patch":
            return "op-1"
        if verb == "sql operations describe":
            assert "op-1" in line
            return next(self.statuses)
        return "RUNNABLE"  # what the instance's state read six seconds into a real start


def test_a_window_waits_for_cloud_sqls_operation_not_the_instances_state() -> None:
    cloud = FakeCloudSql(["RUNNING\t", "RUNNING\t", "DONE\t"])
    naps: list[float] = []

    state = change_activation("ALWAYS", cloud, sleep=naps.append)

    assert state == "RUNNABLE"
    assert naps == [10.0, 10.0]
    assert cloud.calls == [
        "sql instances patch",
        *["sql operations describe"] * 3,
        "sql instances describe",
    ]


def test_a_failed_operation_is_raised() -> None:
    cloud = FakeCloudSql(["DONE\tThe instance couldn't start."])

    with pytest.raises(RuntimeError, match="couldn't start"):
        change_activation("ALWAYS", cloud, sleep=lambda _: None)


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


def test_a_failed_command_never_shows_a_password() -> None:
    fails = [sys.executable, "-c", "raise SystemExit(3)", "--password=s3cret-value"]

    with pytest.raises(subprocess.CalledProcessError) as info:
        gcloud.run(fails)

    assert info.value.returncode == 3
    assert info.value.cmd[-1] == "--password=<hidden>"
    assert "s3cret-value" not in str(info.value)
    assert info.value.__suppress_context__


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


def test_the_reader_loses_what_cloud_sql_gives_new_users() -> None:
    # A user created through the Cloud SQL API joins cloudsqlsuperuser, which owns the
    # database, and may create roles and databases; measured on the instance.
    statements = [line.strip() for line in GRANTS.splitlines() if line.strip()]

    assert statements[:2] == [
        "REVOKE cloudsqlsuperuser FROM facts_reader;",
        "ALTER ROLE facts_reader NOCREATEDB NOCREATEROLE;",
    ]
