"""Value linking for the data agent: companies, metric names, coverage and notes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from copilot.sql.linking import DEFINITIONS, FactsLinker

SCHEMA = """
CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL);
CREATE TABLE annual_values (cik INTEGER, metric TEXT, fiscal_year INTEGER, value REAL);
CREATE TABLE metrics (metric TEXT PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO companies VALUES
    (21344, 'KO', 'Coca-Cola'), (66740, 'MMM', '3M'), (1, NULL, 'Foot Locker'), (2, 'XYZ', 'Block');
INSERT INTO annual_values VALUES
    (21344, 'revenue', 2018, 1.0), (21344, 'revenue', 2022, 2.0), (66740, 'revenue', 2020, 3.0);
INSERT INTO metrics VALUES ('revenue', 'Revenue'), ('eps_diluted', 'Diluted EPS');
"""


@pytest.fixture
def linker(tmp_path: Path) -> FactsLinker:
    path = tmp_path / "facts.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return FactsLinker.read(path)


def test_named_companies_come_first_with_their_cik_and_years(linker: FactsLinker) -> None:
    hints = linker.hints("Did Coke grow faster than MMM, and what about Tesla?")

    assert hints[0] == (
        "\"Coca-Cola\" is companies.name = 'Coca-Cola' (cik 21344); "
        "its annual values cover fiscal 2018 to 2022."
    )
    assert hints[1].startswith("\"3M\" is companies.name = '3M' (cik 66740)")
    assert hints[2] == (
        "The database holds only these companies: 3M, Block, Coca-Cola, Foot Locker. "
        "Any other company is not in it."
    )


def test_every_question_gets_the_metric_names_and_notes(linker: FactsLinker) -> None:
    hints = linker.hints("Which company had the highest revenue?")

    assert hints[0].startswith("The database holds only these companies")
    assert hints[1] == (
        "annual_values.metric takes only these values: eps_diluted (Diluted EPS), "
        "revenue (Revenue)."
    )
    assert DEFINITIONS in hints
    assert hints[-1] == "Name companies in results by companies.name, not by cik."


def test_companies_without_values_and_word_like_names(linker: FactsLinker) -> None:
    assert linker.company_hint("Foot Locker").endswith("(cik 1); it has no annual values.")
    assert not linker.hints("the block of shares")[0].startswith('"Block"')
    assert linker.hints("Block's revenue")[0].startswith('"Block" is companies.name')
