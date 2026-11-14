"""Team-draft interleaving, the search page's backend, and its tally (step 9.4)."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any

import pytest

from copilot.api.search import RANKERS, InterleavedSearch, MemorySearchLog
from copilot.eval.interleaving import clicked, tally
from copilot.retrieval.interleaving import sign_test, team_draft, winner
from copilot.retrieval.query import CompanyMatcher, Filing
from copilot.retrieval.search import Hit, Mode


def hit(name: str, doc: str = "ACME_2022_10K", page: int = 3) -> Hit:
    return Hit(name, 0.5, doc, 0, (page,), "Item 7", f"The passage {name}.")


def ids(placed: Sequence[object]) -> list[str]:
    return [entry.hit.point_id for entry in placed]  # type: ignore[attr-defined]


def test_each_team_places_its_best_result_not_yet_shown() -> None:
    a = [hit("1"), hit("2"), hit("3")]
    b = [hit("2"), hit("4"), hit("1")]

    placed = team_draft(a, b, 4, random.Random(0))

    assert sorted(ids(placed)) == ["1", "2", "3", "4"]  # "1" and "2" shown once
    teams = [entry.team for entry in placed]
    assert teams.count("a") == teams.count("b") == 2  # the team behind always picks next
    first = {entry.hit.point_id: entry.team for entry in placed}
    assert first["3"] == "a"
    assert first["4"] == "b"


def test_the_coin_decides_who_picks_first_in_a_tied_round() -> None:
    a, b = [hit("1")], [hit("2")]

    leads = {team_draft(a, b, 1, random.Random(seed))[0].team for seed in range(20)}

    assert leads == {"a", "b"}


def test_a_short_ranking_leaves_the_rest_to_the_other() -> None:
    placed = team_draft([hit("1")], [hit("2"), hit("3"), hit("4")], 4, random.Random(1))

    assert sorted(ids(placed)) == ["1", "2", "3", "4"]
    assert [entry.team for entry in placed].count("b") == 3
    assert team_draft([], [], 3, random.Random(0)) == []


def test_the_team_with_more_clicks_wins_a_search() -> None:
    teams = ["a", "b", "a", "b"]

    assert winner(teams, [0, 2]) == "a"
    assert winner(teams, [1, 1, 3]) == "b"  # a result clicked twice counts once
    assert winner(teams, [0, 1]) == "tie"
    assert winner(teams, []) is None
    assert winner(teams, [9]) is None  # no such result


def test_the_sign_test_on_decided_searches() -> None:
    assert sign_test(0, 0) == 1.0
    assert sign_test(5, 5) == 1.0
    assert sign_test(10, 0) == pytest.approx(2 / 1024)
    assert sign_test(0, 10) == sign_test(10, 0)


class Ranker:
    """Two fixed rankings, by mode, recording what it was asked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, Mode, int, Sequence[str] | None]] = []

    def search(
        self,
        query: str,
        mode: Mode = "hybrid",
        limit: int = 20,
        doc_names: Sequence[str] | None = None,
    ) -> list[Hit]:
        self.asked.append((query, mode, limit, doc_names))
        if mode == "dense":
            return [hit("d1"), hit("s1"), hit("d2")]
        return [hit("s1"), hit("h1"), hit("h2")]


FILINGS = [Filing("ACME_2022_10K", "Acme", "10k", 2022)]


def search_page(log: MemorySearchLog) -> tuple[InterleavedSearch, Ranker]:
    ranker = Ranker()
    matcher = CompanyMatcher(["Acme"], {"Acme": None})
    return InterleavedSearch(ranker, matcher, FILINGS, log, results=4, seed=0), ranker


def test_a_search_interleaves_both_rankings_in_the_querys_filings() -> None:
    log = MemorySearchLog()
    page, ranker = search_page(log)

    found = page.search("Acme's new plants in 2022")

    assert [mode for _, mode, _, _ in ranker.asked] == [RANKERS["a"], RANKERS["b"]]
    assert ranker.asked[0][3] == ["ACME_2022_10K"]  # the filings the query names
    assert [result["position"] for result in found["results"]] == [0, 1, 2, 3]
    assert found["results"][0]["label"] == "Acme, Form 10-K for fiscal 2022, PDF page 4"
    record = log.records[found["search_id"]]
    assert sorted(record["teams"]) == ["a", "a", "b", "b"]
    assert record["overlap"] == 1  # "s1" was in both rankings
    assert "query" not in record  # the reader's words are never kept


def test_a_click_credits_the_team_that_placed_the_result_once() -> None:
    log = MemorySearchLog()
    page, _ = search_page(log)
    found = page.search("Acme's new plants in 2022")
    search_id = found["search_id"]
    teams = log.records[search_id]["teams"]

    assert page.click(search_id, 2) is True
    assert page.click(search_id, 2) is True  # counted once
    assert page.click(search_id, 9) is False
    assert page.click("not-held", 0) is False
    assert log.records[search_id]["clicks"] == {2: teams[2]}


def test_the_tally_counts_wins_and_tests_them() -> None:
    records: list[dict[str, Any]] = [
        {"teams": ["a", "b"], "click_0": "a", "overlap": 1},
        {"teams": ["b", "a"], "click_1": "a", "overlap": 3},
        {"teams": ["a", "b"], "clicks": {0: "a", 1: "b"}},  # a memory log's tie
        {"teams": ["a", "b"]},  # no click
    ]

    found = tally(records)

    assert clicked(records[2]) == [0, 1]
    assert (found["searches"], found["with_clicks"]) == (4, 3)
    assert found["wins"] == {"a": 2, "b": 0, "tie": 1}
    assert found["clicks"] == {"a": 3, "b": 1}
    assert found["p"] == pytest.approx(0.5)
    assert found["mean_overlap"] == 2.0
