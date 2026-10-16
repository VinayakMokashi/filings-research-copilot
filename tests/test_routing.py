"""The routing eval set: building it, guarding its test side, and scoring routers."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

import pytest

from copilot.eval import routing
from copilot.eval.financebench import ChecksumError, read_jsonl
from copilot.eval.splits import HeldOutError

ROOT = Path(__file__).resolve().parents[1]
VERDICTS: tuple[Literal["accept", "reject"], ...] = ("accept", "accept", "reject")


def _seeds(counts: dict[routing.Route, int]) -> list[routing.Seed]:
    seeds, n = [], 0
    for route, count in counts.items():
        for _ in range(count):
            n += 1
            seeds.append(routing.Seed(seed=f"s{n:02d}", route=route, query=f"{route} question {n}"))
    return seeds


def _candidates(seeds: list[routing.Seed]) -> list[routing.Candidate]:
    rows = []
    for seed in seeds:
        for k, verdict in enumerate(VERDICTS):
            rows.append(
                routing.Candidate(
                    seed=seed.seed,
                    query=f"{seed.query} rewrite {k}",
                    model="test-model",
                    verdict=verdict,
                    reason=None if verdict == "accept" else "surplus",
                )
            )
    return rows


def test_parse_paraphrases_strips_list_markers_and_quotes() -> None:
    text = '1. First rewrite\n\n- "Second rewrite"\n\u2022 Third rewrite\n2) Fourth\n'

    assert routing.parse_paraphrases(text) == [
        "First rewrite",
        "Second rewrite",
        "Third rewrite",
        "Fourth",
    ]


def test_normalise_replaces_unicode_hyphens_and_extra_spaces() -> None:
    assert routing.normalise("Walmart 10\u2011K  e\u2010commerce ") == "Walmart 10-K e-commerce"


def test_paraphrase_prompt_carries_the_route_definition() -> None:
    seed = routing.Seed(seed="s01", route="hybrid", query="What drove the margin change?")

    system_message, user_message = routing.paraphrase_messages(seed)

    assert "three different ways" in system_message["content"]
    assert routing.ROUTE_DEFINITIONS["hybrid"] in user_message["content"]
    assert user_message["content"].endswith("Query: What drove the margin change?")


def test_assign_splits_puts_30_percent_of_each_route_in_test() -> None:
    seeds = _seeds({"doc": 15, "brief": 8, "decline": 10})

    sides = routing.assign_splits(seeds)

    test_counts = Counter(s.route for s in seeds if sides[s.seed] == "test")
    assert test_counts == {"doc": 5, "brief": 2, "decline": 3}
    assert routing.assign_splits(seeds) == sides


def test_build_keeps_each_seed_with_its_paraphrases() -> None:
    seeds = _seeds({"doc": 4, "data": 4})

    queries = routing.build(seeds, _candidates(seeds))

    assert len(queries) == 24
    assert [q.id for q in queries[:3]] == ["r001", "r002", "r003"]
    assert [q.origin for q in queries[:3]] == ["seed", "paraphrase", "paraphrase"]
    sides_by_seed = defaultdict(set)
    for q in queries:
        sides_by_seed[q.seed].add(q.split)
    assert all(len(sides) == 1 for sides in sides_by_seed.values())
    assert "rewrite 2" not in " ".join(q.query for q in queries)


def test_build_needs_a_verdict_for_every_candidate() -> None:
    seeds = _seeds({"doc": 2})
    candidates = _candidates(seeds)
    candidates[0] = candidates[0].model_copy(update={"verdict": None})

    with pytest.raises(ValueError, match="no verdict"):
        routing.build(seeds, candidates)


def test_build_needs_two_accepted_paraphrases_per_seed() -> None:
    seeds = _seeds({"doc": 2})
    candidates = [c for c in _candidates(seeds) if c.query != "doc question 1 rewrite 1"]

    with pytest.raises(ValueError, match="s01"):
        routing.build(seeds, candidates)


def test_build_rejects_duplicate_queries() -> None:
    seeds = _seeds({"doc": 2})
    candidates = _candidates(seeds)
    candidates[0] = candidates[0].model_copy(update={"query": "DOC QUESTION 2"})

    with pytest.raises(ValueError, match="Duplicate"):
        routing.build(seeds, candidates)


def test_the_test_side_is_held_out_and_checksummed(tmp_path: Path) -> None:
    seeds = _seeds({"doc": 10, "data": 10})
    queries_file, checksums_file = tmp_path / "queries.jsonl", tmp_path / "checksums.json"
    routing.write_set(routing.build(seeds, _candidates(seeds)), queries_file, checksums_file)

    with pytest.raises(HeldOutError):
        routing.load_queries("test", path=queries_file, checksums_path=checksums_file)
    dev = routing.load_queries("dev", path=queries_file, checksums_path=checksums_file)
    assert len(dev) == 42
    test = routing.load_queries(
        "test", allow_test=True, path=queries_file, checksums_path=checksums_file
    )
    assert len(test) == 18

    queries_file.write_text(
        queries_file.read_text(encoding="utf-8").replace("doc question", "doc query"),
        encoding="utf-8",
    )
    with pytest.raises(ChecksumError, match="dev"):
        routing.load_queries("dev", path=queries_file, checksums_path=checksums_file)


def test_score_marks_each_prediction(tmp_path: Path) -> None:
    queries = routing.build(_seeds({"doc": 1}), _candidates(_seeds({"doc": 1})))
    predictions = {queries[0].id: "doc", queries[1].id: "data", queries[2].id: "doc"}

    rows = routing.score(queries, predictions)

    assert [row["accuracy"] for row in rows] == [1.0, 0.0, 1.0]
    assert rows[1]["predicted"] == "data"
    with pytest.raises(ValueError, match="1 missing"):
        routing.score(queries, {queries[0].id: "doc", queries[1].id: "doc"})

    path = tmp_path / "routes.jsonl"
    path.write_text(json.dumps({"id": "r001", "route": "doc"}) + "\n", encoding="utf-8")
    assert routing.read_predictions(path) == {"r001": "doc"}


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("Hi there!", "smalltalk"),
        ("Should I buy Nike stock right now?", "decline"),
        ("Draft a memo on Coca-Cola's capital allocation.", "brief"),
        ("What was 3M's capital expenditure in fiscal 2018?", "data"),
        ("What was Netflix's operating margin, and what drove the change?", "hybrid"),
        ("What risks does Netflix list in its 10-K?", "doc"),
    ],
)
def test_keyword_baseline(query: str, route: routing.Route) -> None:
    assert routing.keyword_route(query) == route


def test_majority_route_breaks_ties_by_route_order() -> None:
    queries = routing.build(
        _seeds({"data": 2, "doc": 2}), _candidates(_seeds({"data": 2, "doc": 2}))
    )

    assert routing.majority_route(queries) == "doc"


def test_committed_routing_set_is_consistent() -> None:
    records = read_jsonl(ROOT / routing.QUERIES_FILE)
    queries = [routing.RoutingQuery.model_validate(r) for r in records]
    recorded = routing.Checksums.model_validate_json(
        (ROOT / routing.CHECKSUMS_FILE).read_text(encoding="utf-8")
    )

    assert routing.checksums(queries) == recorded
    assert len(queries) == 198
    by_seed: dict[str, list[routing.RoutingQuery]] = defaultdict(list)
    for q in queries:
        by_seed[q.seed].append(q)
    assert len(by_seed) == 66
    for members in by_seed.values():
        assert sorted(q.origin for q in members) == ["paraphrase", "paraphrase", "seed"]
        assert len({q.split for q in members}) == 1
        assert len({q.route for q in members}) == 1
    assert Counter(q.split for q in queries) == {"dev": 138, "test": 60}
