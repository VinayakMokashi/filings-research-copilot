"""The SQL eval set: building it, comparing rows, scoring predictions, the committed set."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from copilot.eval import sql
from copilot.eval.financebench import ChecksumError, read_jsonl
from copilot.eval.splits import HeldOutError
from copilot.facts.database import SCHEMA, connect_read_only

ROOT = Path(__file__).resolve().parents[1]
FACTS_DB = ROOT / "data" / "processed" / "facts.db"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A small facts database with two companies, opened read-only like the real one."""
    path = tmp_path / "facts.db"
    setup = sqlite3.connect(path)
    setup.executescript(SCHEMA)
    setup.executemany(
        "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "ACME", "Acme", "ACME CORP", "Industrials", "1231"),
            (2, None, "Bolt", "BOLT INC", "Utilities", "0131"),
        ],
    )
    setup.executemany(
        "INSERT INTO annual_values VALUES "
        "(?, 'revenue', ?, NULL, ?, ?, 'USD', 'Revenues', 'x', ?, ?, 'x')",
        [
            (1, 2021, "2021-12-31", 100.0, "2022-02-01", 100.0),
            (2, 2021, "2022-01-31", 250.0, "2022-03-01", 250.0),
        ],
    )
    setup.commit()
    setup.close()
    readonly = connect_read_only(path)
    yield readonly
    readonly.close()


def _source() -> list[sql.SourceQuestion]:
    return [
        sql.SourceQuestion(
            id="s01",
            difficulty="easy",
            category="lookup",
            question="What was Acme's revenue in 2021?",
            gold_sql="SELECT a.value FROM annual_values AS a JOIN companies AS c USING (cik) "
            "WHERE c.name = 'Acme' AND a.fiscal_year = 2021",
        ),
        sql.SourceQuestion(
            id="s02",
            difficulty="medium",
            category="ranking",
            question="Rank the companies by 2021 revenue.",
            gold_sql="SELECT c.name, a.value FROM annual_values AS a "
            "JOIN companies AS c USING (cik) ORDER BY a.value DESC",
        ),
        sql.SourceQuestion(
            id="s03",
            difficulty="easy",
            category="unanswerable",
            question="What is Acme's share price?",
            reason="Prices are not in the database.",
        ),
    ]


@pytest.mark.parametrize(
    ("gold", "predicted", "match"),
    [
        ([[1.0]], [[1.0]], True),
        ([["Acme", 100.0], ["Bolt", 250.0]], [["Bolt", 250.0], ["Acme", 100.0]], True),  # row order
        ([["Acme", 100.0]], [[100.0, "Acme"]], True),  # column order
        ([[0.125]], [[0.13]], True),  # rounded half up to two places
        ([["2010"]], [[2010]], True),  # numeric strings are numbers
        ([["Acme"]], [["Acme", 100.0]], True),  # an extra column is fine
        ([["Acme", 100.0]], [["Acme"]], False),  # a missing column is not
        ([[1.0]], [[1.0], [1.0]], False),  # an extra row is not
        (
            [["Acme", 1.0], ["Bolt", 2.0]],
            [["Acme", 2.0], ["Bolt", 1.0]],
            False,
        ),  # rows must line up
        ([], [], True),
    ],
)
def test_rows_match(gold: list[list[object]], predicted: list[list[object]], match: bool) -> None:
    assert sql.rows_match(gold, predicted) is match


def test_a_source_question_needs_sql_or_a_reason() -> None:
    with pytest.raises(ValueError, match="either gold_sql or a reason"):
        sql.SourceQuestion(id="s9", difficulty="easy", category="lookup", question="?")


def test_build_records_gold_rows_and_splits(conn: sqlite3.Connection) -> None:
    questions = {q.id: q for q in sql.build(_source(), conn)}

    assert questions["s01"].expected == [[100.0]]
    assert questions["s02"].expected == [["Bolt", 250.0], ["Acme", 100.0]]
    assert (questions["s03"].answerable, questions["s03"].expected) == (False, None)
    assert {q.split for q in questions.values()} <= {"dev", "test"}


def test_assign_splits_takes_30_percent_of_each_category() -> None:
    source = [
        sql.SourceQuestion(
            id=f"s{i:02d}", difficulty="easy", category=cat, question="?", reason="r"
        )
        for i, cat in enumerate(["lookup"] * 10 + ["ratio"] * 5 + ["growth"])
    ]

    sides = sql.assign_splits(source)

    test = Counter(q.category for q in source if sides[q.id] == "test")
    assert test == {"lookup": 3, "ratio": 2}
    assert sql.assign_splits(source) == sides


def test_scoring_rewards_right_answers_and_right_refusals(conn: sqlite3.Connection) -> None:
    questions = sql.build(_source(), conn)
    predictions = {
        "s01": sql.Prediction(id="s01", sql="SELECT 100.0"),
        "s02": sql.Prediction(id="s02", sql="SELECT name FROM companies"),
        "s03": sql.Prediction(id="s03", declined=True),
    }

    rows = {row["id"]: row for row in sql.score(questions, predictions, conn)}

    assert [rows[i]["accuracy"] for i in ("s01", "s02", "s03")] == [1.0, 0.0, 1.0]
    assert rows["s03"]["answerable"] == "unanswerable"


def test_declining_an_answerable_question_is_wrong(conn: sqlite3.Connection) -> None:
    questions = sql.build(_source(), conn)
    predictions = {q.id: sql.Prediction(id=q.id, declined=True) for q in questions}

    rows = sql.score(questions, predictions, conn)

    assert [row["accuracy"] for row in rows] == [0.0, 0.0, 1.0]


def test_broken_and_writing_queries_score_zero_with_the_error(conn: sqlite3.Connection) -> None:
    questions = sql.build(_source(), conn)
    predictions = {
        "s01": sql.Prediction(id="s01", sql="SELECT nonsense FROM nowhere"),
        "s02": sql.Prediction(id="s02", sql="DELETE FROM companies"),
        "s03": sql.Prediction(id="s03", declined=True),
    }

    rows = {row["id"]: row for row in sql.score(questions, predictions, conn)}

    assert (rows["s01"]["accuracy"], rows["s02"]["accuracy"]) == (0.0, 0.0)
    assert "no such table" in rows["s01"]["error"]
    assert "readonly" in rows["s02"]["error"]
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 2


def test_runaway_queries_are_stopped(conn: sqlite3.Connection) -> None:
    runaway = (
        "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT COUNT(*) FROM n"
    )

    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        sql.run_query(conn, runaway, max_steps=100_000)


def test_the_test_side_is_held_out_and_checksummed(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    questions = sql.build(_source(), conn)
    questions = [
        q.model_copy(update={"split": "test" if q.id == "s02" else "dev"}) for q in questions
    ]
    files = {"path": tmp_path / "q.jsonl", "checksums_path": tmp_path / "c.json"}
    sql.write_set(questions, files["path"], files["checksums_path"])

    with pytest.raises(HeldOutError):
        sql.load_questions("test", path=files["path"], checksums_path=files["checksums_path"])
    dev = sql.load_questions("dev", path=files["path"], checksums_path=files["checksums_path"])
    assert [q.id for q in dev] == ["s01", "s03"]

    files["path"].write_text(
        files["path"].read_text(encoding="utf-8").replace("Acme's", "Bolt's"), encoding="utf-8"
    )
    with pytest.raises(ChecksumError):
        sql.load_questions("dev", path=files["path"], checksums_path=files["checksums_path"])


def test_committed_set_is_consistent() -> None:
    records = read_jsonl(ROOT / sql.QUESTIONS_FILE)
    questions = [sql.SqlQuestion.model_validate(r) for r in records]
    recorded = sql.Checksums.model_validate_json(
        (ROOT / sql.CHECKSUMS_FILE).read_text(encoding="utf-8")
    )

    assert sql.checksums(questions) == recorded
    assert len(questions) == len({q.id for q in questions}) == 42
    assert sum(not q.answerable for q in questions) == 10
    assert all(q.expected for q in questions if q.answerable)
    assert [q.id for q in questions] == [q.id for q in sql.load_source(ROOT / sql.SOURCE_FILE)]


def test_every_gold_query_compiles_against_the_schema() -> None:
    schema = sqlite3.connect(":memory:")
    schema.executescript(SCHEMA)
    for question in sql.load_source(ROOT / sql.SOURCE_FILE):
        if question.gold_sql is not None:
            schema.execute(f"EXPLAIN {question.gold_sql}")  # raises on unknown tables or columns


@pytest.mark.integration
@pytest.mark.skipif(not FACTS_DB.exists(), reason="needs the facts database (poe build-facts)")
def test_gold_queries_still_return_the_recorded_rows() -> None:
    conn = connect_read_only(FACTS_DB)
    try:
        for record in read_jsonl(ROOT / sql.QUESTIONS_FILE):
            question = sql.SqlQuestion.model_validate(record)
            if question.answerable:
                rows = sql.run_query(conn, question.gold_sql or "")
                assert sql.rows_match(question.expected or [], rows), question.id
    finally:
        conn.close()
