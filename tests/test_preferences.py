"""Preference pairs from readers' picks and ratings and from the validator (step 9.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from copilot.eval.preferences import (
    MAX_PAIRS_A_QUESTION,
    VALIDATOR,
    exchange_validator_pairs,
    rating_pairs,
    retry_pairs,
    run_validator_pairs,
)
from copilot.llm import assistant

QUESTION = "What did Acme spend on new plants in fiscal 2022?"
SOURCE = {
    "number": 1,
    "label": "Acme, PDF page 41",
    "doc_name": "ACME_2022_10K",
    "page": 40,
    "text": "Acme built two plants in fiscal 2022 for $420 million.",
}


def exchange(request_id: str, text: str, **fields: Any) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "standalone": QUESTION,
        "kind": "doc",
        "text": text,
        "sources": [SOURCE],
        "validation": {"checked": True, "faithful": True},
        "revisions": 0,
        "draft": None,
    } | fields


GOOD = "Acme spent $420 million on two new plants [1]."
BAD = "Acme spent money on plants."


def test_a_pick_makes_a_pair_with_the_answer_prompt_rebuilt() -> None:
    picks = [
        {"chosen": "second", "first": exchange("r1", BAD), "second": exchange("r2", GOOD)},
        {"chosen": "neither", "first": exchange("r3", BAD), "second": exchange("r4", GOOD)},
        {"chosen": "first", "first": exchange("r5", GOOD), "second": exchange("r6", GOOD)},
    ]

    (pair,) = retry_pairs(picks)

    assert (pair.chosen, pair.rejected, pair.ids) == (GOOD, BAD, ("r2", "r1"))
    assert (pair.source, pair.prompt_kind) == ("retry", "sources")
    system, asked = pair.prompt
    assert system["role"] == "system"
    assert system["content"].startswith("You answer questions about public companies")
    assert asked["content"].startswith(f"Question: {QUESTION}")
    assert "[1] Acme, PDF page 41\nAcme built two plants" in asked["content"]
    assert pair.trl() == {
        "prompt": pair.prompt,
        "chosen": [assistant(GOOD)],
        "rejected": [assistant(BAD)],
    }
    assert json.loads(json.dumps(pair.meta())) == {
        "source": "retry",
        "labeller": "a reader",
        "ids": ["r2", "r1"],
        "prompt": "sources",
    }


def test_answers_from_different_sources_keep_only_the_question() -> None:
    elsewhere = SOURCE | {"page": 41}
    picks = [
        {
            "chosen": "first",
            "first": exchange("r1", GOOD),
            "second": exchange("r2", BAD, sources=[elsewhere]),
        }
    ]

    (pair,) = retry_pairs(picks)

    assert pair.prompt_kind == "question"
    assert pair.prompt == [{"role": "user", "content": QUESTION}]


def test_a_hybrid_answer_gets_the_hybrids_prompt() -> None:
    picks = [
        {
            "chosen": "first",
            "first": exchange("r1", GOOD, kind="hybrid"),
            "second": exchange("r2", BAD, kind="hybrid"),
        }
    ]

    (pair,) = retry_pairs(picks)

    assert "Facts database" in pair.prompt[0]["content"]  # the hybrid's own instructions


def test_opposite_ratings_of_one_question_make_pairs_up_to_a_cap() -> None:
    ratings: list[dict[str, Any]] = [{"rating": "up", "exchange": exchange("u0", GOOD)}]
    ratings += [
        {"rating": "down", "exchange": exchange(f"d{n}", f"{BAD} ({n})")} for n in range(12)
    ]
    ratings += [
        {"rating": "down", "exchange": exchange("x", BAD, standalone="Another question?")},
        {"rating": "up", "exchange": None},  # a rating whose answer wasn't held
    ]

    pairs = rating_pairs(ratings)

    assert len(pairs) == MAX_PAIRS_A_QUESTION
    assert {pair.chosen for pair in pairs} == {GOOD}
    assert {pair.labeller for pair in pairs} == {"readers' ratings"}


def test_a_revision_that_passed_makes_a_pair_with_the_draft_it_replaced() -> None:
    ratings = [
        {"rating": "up", "exchange": exchange("r1", GOOD, revisions=1, draft=BAD)},
        {"rating": "down", "exchange": exchange("r2", GOOD)},  # never revised
        {
            "rating": "down",
            "exchange": exchange(
                "r3", GOOD, revisions=2, draft=BAD, validation={"checked": True, "faithful": False}
            ),
        },
    ]

    (pair,) = exchange_validator_pairs(ratings)

    assert (pair.chosen, pair.rejected, pair.labeller) == (GOOD, BAD, VALIDATOR)
    assert pair.ids == ("r1",)


def test_a_local_runs_revisions_make_pairs_by_question_id(tmp_path: Path) -> None:
    answers = {
        "q1": exchange("q1", GOOD, revisions=1),
        "q2": exchange("q2", GOOD),
        "q3": exchange("q3", GOOD, revisions=1),
    }
    drafts = {"q1": {"text": BAD}, "q3": {"text": BAD}}

    pairs = run_validator_pairs(answers, drafts, {"q1": QUESTION, "q2": QUESTION})

    assert [pair.ids for pair in pairs] == [("q1",)]  # q3's question isn't in the split
    assert pairs[0].prompt[1]["content"].startswith(f"Question: {QUESTION}")
