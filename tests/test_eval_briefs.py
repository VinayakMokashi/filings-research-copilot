"""The brief set and its rubric grades: every case well formed, verdicts read item by item."""

from __future__ import annotations

import json

import pytest

from copilot.eval import briefs
from copilot.eval.briefs import BriefCase
from copilot.eval.splits import read_split_file
from copilot.llm import FakeLLM

CASE = BriefCase(
    id="b99",
    company="Acme",
    filing="ACME_2022_10K",
    request="Brief on Acme's 2022.",
    rubric=["States revenue, with a figure.", "Names a risk.", "Covers debt."],
)


def test_the_brief_set_is_well_formed_and_uses_dev_companies_only() -> None:
    cases = briefs.load_briefs()

    assert len(cases) == 12
    assert len({case.id for case in cases}) == len(cases)
    assert all(4 <= len(case.rubric) <= 5 for case in cases)
    split = read_split_file()
    assert {case.company for case in cases} <= set(split.dev_companies)


def test_grade_reads_each_item_and_counts_a_missing_one_as_not_met() -> None:
    reply = {
        "items": [{"n": 1, "met": True, "reason": "It gives $10 billion."}, {"n": 3, "met": True}]
    }
    llm = FakeLLM([json.dumps(reply)])

    result = briefs.grade(llm, CASE, "Revenue was $10 billion [1].")

    assert result.met == [True, False, True]
    assert result.score == pytest.approx(2 / 3)
    assert llm.calls[0].role == "fast"
    assert "3. Covers debt." in llm.calls[0].messages[1]["content"]


def test_an_empty_brief_meets_nothing_without_a_call() -> None:
    llm = FakeLLM([])

    assert briefs.grade(llm, CASE, "  ").met == [False, False, False]
    assert llm.calls == []


def test_a_reply_without_verdicts_is_an_error_not_a_pass() -> None:
    result = briefs.grade(FakeLLM(["The brief looks fine."]), CASE, "Revenue was $10 billion [1].")

    assert result.met == [False, False, False]
    assert result.error is not None


def test_agreement_is_the_share_graded_alike() -> None:
    assert briefs.agreement([True, False, True, True], [True, True, True, False]) == 0.5
    with pytest.raises(ValueError, match="Two gradings"):
        briefs.agreement([True], [])
