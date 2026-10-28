"""The facts tables in PostgreSQL, and where the data agent's queries run (step 8.4).

The integration test needs the Compose Postgres (`uv run poe services-up`); it loads a
small facts database into a database and a role of its own, and drops both afterwards.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import SecretStr
from text2sql.db import DatabaseUnavailableError
from text2sql.execution import QueryResult, SQLExecutionError, execute_query

from copilot.config import Settings, get_settings
from copilot.facts import postgres as facts_pg
from copilot.facts.database import SCHEMA
from copilot.llm import FakeLLM, Message, ModelRole
from copilot.sql import executor as executor_module
from copilot.sql.agent import build_pipeline
from copilot.sql.executor import FactsExecutor

ROWS = """
INSERT INTO companies VALUES
    (66740, 'MMM', '3M', '3M CO', 'Industrials', '12-31'),
    (21344, 'KO', 'Coca-Cola', 'COCA COLA CO', 'Consumer Staples', '12-31');
INSERT INTO filings VALUES
    ('0000066740-19-000010', 66740, '10-K', '2019-02-07', 2018, 'FY', '2018-12-31', 2018),
    ('0000021344-19-000014', 21344, '10-K', '2019-02-21', 2018, 'FY', '2018-12-31', 2018);
INSERT INTO metrics VALUES
    ('capital_expenditure', 'Capital expenditure', 'Cash paid for PP&E.', 'duration', 'USD',
     'cash flow', 'priority');
INSERT INTO annual_values VALUES
    (66740, 'capital_expenditure', 2018, '2018-01-01', '2018-12-31', 1577000000.0, 'USD',
     'PaymentsToAcquirePropertyPlantAndEquipment', '0000066740-19-000010', '2019-02-07',
     1577000000.0, '0000066740-19-000010'),
    (21344, 'capital_expenditure', 2018, '2018-01-01', '2018-12-31', 1347000000.0, 'USD',
     'PaymentsToAcquirePropertyPlantAndEquipment', '0000021344-19-000014', '2019-02-21',
     1347000000.0, '0000021344-19-000014');
"""


@pytest.fixture
def facts_db(tmp_path: Path) -> Path:
    path = tmp_path / "processed" / "facts.db"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA + ROWS)
    return path


def test_the_postgres_schema_keeps_eight_byte_floats() -> None:
    assert " REAL" not in facts_pg.POSTGRES_SCHEMA
    assert facts_pg.POSTGRES_SCHEMA.count("DOUBLE PRECISION") == SCHEMA.count(" REAL")


def test_text_sorts_in_sqlite_byte_order() -> None:
    assert facts_pg.POSTGRES_SCHEMA.count('TEXT COLLATE "C"') == SCHEMA.count(" TEXT")


def test_tables_are_copied_parents_first() -> None:
    created = [line.split()[2] for line in SCHEMA.splitlines() if line.startswith("CREATE TABLE")]
    assert list(facts_pg.TABLES) == created


def test_the_reader_url_names_the_role_and_a_short_connect_timeout() -> None:
    url = facts_pg.reader_url("postgresql://admin:pw@10.0.0.5:5432/postgres", "s3cret")
    assert url == "postgresql://facts_reader:s3cret@10.0.0.5:5432/facts?connect_timeout=2"
    assert facts_pg.database_url("postgresql://a:b@h:1/x", "facts") == (
        "postgresql://a:b@h:1/facts"
    )


def _result(target: object) -> QueryResult:
    return QueryResult(sql="SELECT 1", columns=["x"], rows=[(str(target),)], truncated=False,
                       elapsed_s=0.0)  # fmt: skip


def test_queries_fall_back_to_the_file_while_the_server_is_down(
    monkeypatch: pytest.MonkeyPatch, facts_db: Path
) -> None:
    server = {"up": False}
    calls: list[str] = []

    def fake_execute(
        target: object, sql: str, max_rows: int, timeout_s: float, dialect: str
    ) -> QueryResult:
        calls.append(str(target))
        if str(target).startswith("postgresql://") and not server["up"]:
            raise DatabaseUnavailableError("The database could not be reached.")
        return _result(target)

    monkeypatch.setattr(executor_module, "execute_query", fake_execute)
    now = [100.0]
    url, path = "postgresql://r:p@h/facts", facts_db
    run = FactsExecutor(url, path, retry_after_s=60, clock=lambda: now[0])

    assert run("SELECT 1", 10, 5.0, "sqlite").rows == [(str(path),)]
    assert not run.server_up
    run("SELECT 1", 10, 5.0, "sqlite")  # within the minute: straight to the file
    assert calls == [url, str(path), str(path)]

    server["up"], now[0] = True, now[0] + 61
    assert run("SELECT 1", 10, 5.0, "sqlite").rows == [(url,)]


def test_only_what_sqlite_accepts_reaches_the_server(
    monkeypatch: pytest.MonkeyPatch, facts_db: Path
) -> None:
    calls: list[str] = []

    def fake_execute(target: object, *args: object) -> QueryResult:
        calls.append(str(target))
        return _result(target)

    monkeypatch.setattr(executor_module, "execute_query", fake_execute)
    run = FactsExecutor("postgresql://r:p@h/facts", facts_db)
    # A JOIN after WHERE: sqlglot's parser would move it into place; SQLite's refuses it.
    sql = (
        "SELECT c.name FROM annual_values AS a WHERE a.fiscal_year = 2018 "
        "JOIN companies AS c ON c.cik = a.cik"
    )

    with pytest.raises(SQLExecutionError, match='near "JOIN": syntax error'):
        run(sql, 10, 5.0, "sqlite")
    with pytest.raises(SQLExecutionError, match="no such column"):
        run("SELECT no_such_column FROM companies", 10, 5.0, "sqlite")
    assert calls == []


def _models() -> FakeLLM:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        if role == "fast":
            return '{"tables": ["annual_values", "companies"], "answerable": true}'
        return (
            "```sql\nSELECT c.name, ROUND(a.value / 1e6, 1) AS capexMillions FROM annual_values "
            "AS a JOIN companies AS c USING (cik) WHERE c.name LIKE '3%' ORDER BY c.name\n```"
        )

    return FakeLLM(reply)


def test_the_data_agent_uses_the_server_only_for_the_facts_database(facts_db: Path) -> None:
    settings = Settings(
        facts_url=SecretStr("postgresql://r:p@h/facts"), data_dir=facts_db.parent.parent
    )

    default = build_pipeline(settings, _models(), descriptions={})
    other_file = build_pipeline(settings, _models(), db_path=facts_db, descriptions={})

    assert isinstance(default.executor, FactsExecutor)
    assert not isinstance(other_file.executor, FactsExecutor)
    assert not isinstance(build_pipeline(Settings(), _models(), db_path=facts_db,
                                         descriptions={}).executor, FactsExecutor)  # fmt: skip


@pytest.mark.integration
def test_facts_load_into_postgres_and_answer_as_sqlite_does(facts_db: Path) -> None:
    psycopg = pytest.importorskip("psycopg")
    admin = get_settings().database_url
    suffix = uuid.uuid4().hex[:8]
    database, role = f"facts_test_{suffix}", f"facts_reader_{suffix}"
    try:
        assert facts_pg.create_database(admin, database)
        url = facts_pg.database_url(admin, database)
        counts = facts_pg.load(facts_db, url)
        assert counts["annual_values"] == 2
        assert counts["companies"] == 2
        facts_pg.grant_reader(url, "test-only", database, role_name=role)
        reader = facts_pg.reader_url(admin, "test-only", database, role_name=role)

        settings = Settings(facts_url=SecretStr(reader), data_dir=facts_db.parent.parent)
        out = build_pipeline(settings, _models(), descriptions={}).ask(
            "What was 3M's capex in 2018, in millions?", analyze=False
        )
        on_file = execute_query(facts_db, out.result.sql if out.result else "")

        assert out.ok, out.message
        assert out.result is not None
        assert out.result.executed_sql is not None
        assert "ILIKE" in out.result.executed_sql
        assert out.result.columns == on_file.columns == ["name", "capexMillions"]
        assert out.result.rows == on_file.rows == [("3M", 1577.0)]
        with psycopg.connect(reader) as conn, pytest.raises(psycopg.Error):
            conn.execute("DELETE FROM companies")
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'.encode())
            conn.execute(f'DROP ROLE IF EXISTS "{role}"'.encode())
