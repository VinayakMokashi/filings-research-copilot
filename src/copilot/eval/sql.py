"""The SQL eval set: questions over the facts database, with verified gold SQL.

Answerable questions carry gold SQL and the rows it returned when the set was built, after
each result was checked by hand; a predicted query is right when its rows match. The other
questions can't be answered from the database (a company outside the universe, segment
figures, prices, forecasts), and the right response is to decline.

Rows match under the same rules as text2sql-analyst's evaluator: row order and column order
don't matter, numbers are compared at two decimal places, and a prediction may add columns
as long as every gold column is there and the rows line up.
"""

from __future__ import annotations

import json
import random
import sqlite3
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from copilot.eval.financebench import ChecksumError, read_jsonl
from copilot.eval.splits import HeldOutError, records_sha256

DIR = Path("eval/sql")
SOURCE_FILE = DIR / "source.jsonl"
QUESTIONS_FILE = DIR / "questions.jsonl"
CHECKSUMS_FILE = DIR / "checksums.json"

SqlSplit = Literal["dev", "test"]
MAX_STEPS = 50_000_000  # SQLite virtual-machine steps before a query is stopped
_MAX_MAPPINGS = 1_000
_CENT = Decimal("0.01")


class SourceQuestion(BaseModel):
    """A hand-written question: gold SQL if it can be answered, otherwise the reason it can't."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    difficulty: Literal["easy", "medium", "hard"]
    category: str
    question: str
    gold_sql: str | None = None
    reason: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _sql_or_reason(self) -> Self:
        if (self.gold_sql is None) == (self.reason is None):
            raise ValueError(f"{self.id}: give either gold_sql or a reason it can't be answered.")
        return self


class SqlQuestion(SourceQuestion):
    answerable: bool
    expected: list[list[Any]] | None
    split: SqlSplit


class Checksums(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    questions: int
    dev_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    test_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Prediction(BaseModel):
    """A system's response: a query, or a decision to decline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    sql: str | None = None
    declined: bool = False


def load_source(path: Path = SOURCE_FILE) -> list[SourceQuestion]:
    return [SourceQuestion.model_validate(record) for record in read_jsonl(path)]


def run_query(
    conn: sqlite3.Connection, sql: str, max_steps: int = MAX_STEPS
) -> list[tuple[Any, ...]]:
    """Run one statement, stopping it if it runs for more than `max_steps` VM steps."""
    steps = 0

    def tick() -> int:
        nonlocal steps
        steps += 1000
        return 1 if steps > max_steps else 0

    conn.set_progress_handler(tick, 1000)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.set_progress_handler(None, 0)


def assign_splits(questions: Sequence[SourceQuestion], seed: int = 0) -> dict[str, SqlSplit]:
    """Put 30% of each category's questions (rounded half up) in test, chosen at random."""
    by_category: dict[str, list[str]] = {}
    for question in questions:
        by_category.setdefault(question.category, []).append(question.id)
    sides: dict[str, SqlSplit] = {}
    for offset, category in enumerate(sorted(by_category)):
        ids = sorted(by_category[category])
        random.Random(seed + offset).shuffle(ids)
        test_count = (len(ids) * 3 + 5) // 10
        for position, question_id in enumerate(ids):
            sides[question_id] = "test" if position < test_count else "dev"
    return sides


def build(source: Sequence[SourceQuestion], conn: sqlite3.Connection) -> list[SqlQuestion]:
    """Run every gold query, record its rows, and assign the split."""
    sides = assign_splits(source)
    questions = []
    for item in source:
        expected = None
        if item.gold_sql is not None:
            expected = [[_stored(value) for value in row] for row in run_query(conn, item.gold_sql)]
        questions.append(
            SqlQuestion(
                **item.model_dump(),
                answerable=item.gold_sql is not None,
                expected=expected,
                split=sides[item.id],
            )
        )
    return questions


def _stored(value: Any) -> Any:
    """Floats are kept to 6 decimal places, enough for comparison at 2."""
    return round(value, 6) if isinstance(value, float) else value


def checksums(questions: Sequence[SqlQuestion]) -> Checksums:
    def digest(side: SqlSplit) -> str:
        return records_sha256(q.model_dump(mode="json") for q in questions if q.split == side)

    return Checksums(questions=len(questions), dev_sha256=digest("dev"), test_sha256=digest("test"))


def write_set(
    questions: Sequence[SqlQuestion],
    path: Path = QUESTIONS_FILE,
    checksums_path: Path = CHECKSUMS_FILE,
) -> None:
    lines = "".join(
        json.dumps(q.model_dump(mode="json"), ensure_ascii=False) + "\n" for q in questions
    )
    path.write_text(lines, encoding="utf-8", newline="\n")
    checksums_path.write_text(
        checksums(questions).model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def load_questions(
    split: SqlSplit,
    *,
    allow_test: bool = False,
    path: Path = QUESTIONS_FILE,
    checksums_path: Path = CHECKSUMS_FILE,
) -> list[SqlQuestion]:
    """One side of the SQL set, checked against the recorded checksum."""
    if split == "test" and not allow_test:
        raise HeldOutError(
            "The SQL test split is held out for milestone evaluations. "
            "Pass allow_test=True only for one of those."
        )
    records = [record for record in read_jsonl(path) if record["split"] == split]
    recorded = Checksums.model_validate_json(checksums_path.read_text(encoding="utf-8"))
    expected = recorded.dev_sha256 if split == "dev" else recorded.test_sha256
    if records_sha256(records) != expected:
        raise ChecksumError(f"The SQL {split} questions differ from the recorded checksum.")
    return [SqlQuestion.model_validate(record) for record in records]


def normalise(value: Any) -> Any:
    """Numbers (and numeric strings) at two decimal places, rounded half up; text trimmed."""
    if value is None:
        return None
    if isinstance(value, bool):
        value = float(value)
    if isinstance(value, int | float):
        return _round2(Decimal(repr(float(value))))
    text = str(value).strip()
    try:
        return _round2(Decimal(text))
    except ArithmeticError:
        return text


def _round2(number: Decimal) -> float:
    if not number.is_finite():
        return float(number)
    return float(number.quantize(_CENT, rounding=ROUND_HALF_UP)) + 0.0  # -0.0 becomes 0.0


def rows_match(gold: Sequence[Sequence[Any]], predicted: Sequence[Sequence[Any]]) -> bool:
    """True when the prediction holds the gold rows, by the rules in the module docstring."""
    if len(gold) != len(predicted):
        return False
    if not gold:
        return True
    gold_columns = list(zip(*([normalise(v) for v in row] for row in gold), strict=True))
    predicted_columns = list(zip(*([normalise(v) for v in row] for row in predicted), strict=True))

    def key(column: tuple[Any, ...]) -> list[str]:
        return sorted(map(repr, column))

    candidates = [
        [j for j, column in enumerate(predicted_columns) if key(column) == key(gold_column)]
        for gold_column in gold_columns
    ]
    if any(not options for options in candidates):
        return False
    target = Counter(zip(*gold_columns, strict=True))
    for count, mapping in enumerate(_distinct_choices(candidates)):
        if count >= _MAX_MAPPINGS:
            break
        chosen = (predicted_columns[j] for j in mapping)
        if Counter(zip(*chosen, strict=True)) == target:
            return True
    return False


def _distinct_choices(candidates: list[list[int]]) -> Iterator[tuple[int, ...]]:
    """Every way to pick a different prediction column for each gold column."""
    chosen: list[int] = []

    def extend(position: int) -> Iterator[tuple[int, ...]]:
        if position == len(candidates):
            yield tuple(chosen)
            return
        for option in candidates[position]:
            if option not in chosen:
                chosen.append(option)
                yield from extend(position + 1)
                chosen.pop()

    return extend(0)


def score(
    questions: Sequence[SqlQuestion],
    predictions: Mapping[str, Prediction],
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """One row per question: whether the response was right, and any error from its query."""
    expected = {q.id for q in questions}
    missing, extra = expected - predictions.keys(), predictions.keys() - expected
    if missing or extra:
        raise ValueError(
            f"Predictions don't match the questions: {len(missing)} missing, {len(extra)} extra."
        )
    rows = []
    for question in questions:
        prediction = predictions[question.id]
        declined = prediction.declined or prediction.sql is None
        error = None
        if not question.answerable:
            correct = declined
        elif declined:
            correct = False
        else:
            try:
                result = run_query(conn, prediction.sql or "")
                correct = rows_match(question.expected or [], result)
            except sqlite3.Error as exc:
                correct, error = False, str(exc)
        rows.append(
            {
                "id": question.id,
                "category": question.category,
                "difficulty": question.difficulty,
                "answerable": "answerable" if question.answerable else "unanswerable",
                "declined": declined,
                "accuracy": 1.0 if correct else 0.0,
                "error": error,
            }
        )
    return rows


def read_predictions(path: Path) -> dict[str, Prediction]:
    """Predictions as JSON Lines, one per question.

    Each line is `{"id": "s01", "sql": "SELECT ..."}` or `{"id": "s33", "declined": true}`.
    """
    predictions: dict[str, Prediction] = {}
    for record in read_jsonl(path):
        prediction = Prediction.model_validate(record)
        if prediction.id in predictions:
            raise ValueError(f"{path} predicts {prediction.id} more than once.")
        predictions[prediction.id] = prediction
    return predictions
