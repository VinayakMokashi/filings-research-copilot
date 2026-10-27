"""Training questions for the classifier router: prompts, parsing, plans and filters."""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pytest
from pydantic import ValidationError

from copilot.agents.router import ROUTES, Route
from copilot.agents.router_training import (
    PER_BATCH,
    STYLES,
    Batch,
    TrainQuestion,
    assign_splits,
    batch_plan,
    keep_distinct,
    nearest_similarity,
    parse_questions,
    writer_messages,
)

COMPANIES = ["3M", "Adobe", "Boeing", "Coca-Cola", "Nike", "Pfizer", "Walmart", "Intel"]
MEASURES = ["Revenue", "Net income", "Capital expenditure", "Free cash flow", "Total assets"]


def test_the_writer_is_told_the_routes_the_rules_and_its_batch() -> None:
    batch = Batch(3, "hybrid", STYLES[0], ("Nike", "Intel"), ("Revenue",))

    system_message, user_message = writer_messages(batch)

    for route in ROUTES:
        assert f"- {route}: " in system_message["content"]
    assert "Rules for close calls:" in system_message["content"]
    assert "Route: hybrid" in user_message["content"]
    assert f"Write {PER_BATCH} questions." in user_message["content"]
    assert "Nike, Intel" in user_message["content"]
    assert STYLES[0] in user_message["content"]


def test_questions_are_parsed_and_cleaned() -> None:
    hyphen = chr(0x2011)  # a non-breaking hyphen, as models write them
    quoted = chr(34) + "Quoted?" + chr(34)
    reply = json.dumps({"questions": [f"  What was 3M{hyphen}s  capex? ", quoted, "", 7]})

    assert parse_questions(reply) == ["What was 3M-s capex?", "Quoted?"]
    with pytest.raises(ValueError, match="questions"):
        parse_questions('{"items": ["a"]}')


def test_the_plan_covers_every_route_and_repeats_itself() -> None:
    plan = batch_plan(COMPANIES, MEASURES, per_route=40, n=15)

    assert Counter(batch.route for batch in plan) == dict.fromkeys(ROUTES, 3)
    assert len({batch.number for batch in plan}) == len(plan)
    assert plan == batch_plan(COMPANIES, MEASURES, per_route=40, n=15)
    assert set(plan) < set(batch_plan(COMPANIES, MEASURES, per_route=80, n=15))
    assert plan != batch_plan(COMPANIES, MEASURES, per_route=40, n=15, seed=1)
    assert {batch.style for batch in plan[:3]} == set(STYLES[:3])
    assert all(set(batch.companies) <= set(COMPANIES) for batch in plan)
    assert all(len(set(batch.measures)) == 4 for batch in plan)


def test_near_duplicates_and_close_neighbours_are_found() -> None:
    a, b = np.array([1.0, 0.0], dtype=np.float32), np.array([0.0, 1.0], dtype=np.float32)
    close = np.array([0.99, 0.141], dtype=np.float32)
    close /= np.linalg.norm(close)
    vectors = np.stack([a, close, b, a])

    assert keep_distinct(vectors, limit=0.95) == [0, 2]
    assert keep_distinct(vectors, limit=0.999) == [0, 1, 2]
    nearest = nearest_similarity(np.stack([a, b]), np.stack([close]))
    assert nearest[0] == pytest.approx(0.99, abs=1e-3)
    assert nearest[1] == pytest.approx(0.141, abs=1e-3)
    assert len(nearest_similarity(np.stack([a]), np.zeros((0, 2), dtype=np.float32))) == 1


def test_validation_questions_are_a_share_of_each_route() -> None:
    counts: dict[Route, int] = {"doc": 20, "data": 15, "decline": 4}
    routes = [route for route, count in counts.items() for _ in range(count)]

    splits = assign_splits(routes, share=0.1)

    by_route = Counter(route for route, split in zip(routes, splits, strict=True) if split == "val")
    assert by_route == Counter({"doc": 2, "data": 2})  # 0.4 of a decline rounds to none
    assert splits == assign_splits(routes, share=0.1)


def test_a_training_question_needs_a_known_route() -> None:
    fields = {"id": "t0001", "question": "Hi!", "intended": "smalltalk", "style": "terse"}

    good = TrainQuestion.model_validate(fields | {"route": "smalltalk", "split": "train"})
    assert good.route == "smalltalk"
    with pytest.raises(ValidationError):
        TrainQuestion.model_validate(fields | {"route": "weather", "split": "train"})
