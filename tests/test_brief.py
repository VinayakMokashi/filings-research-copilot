"""The brief crew: a plan in sections, specialists' answers checked, one source list, a summary."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from copilot.agents import brief
from copilot.answer.context import Source
from copilot.answer.generate import Answer
from copilot.llm import FakeLLM, LLMError, Message, ModelRole

PLAN: dict[str, Any] = {
    "title": "Acme in fiscal 2022",
    "modules": ["results", "risks"],
    "adapted": ["Acme's 2022 revenue and its change", "Acme's main 2022 risk factors"],
    "sections": [
        {
            "heading": "Results",
            "question": "Acme revenue 2022?",
            "route": "hybrid",
            "module": "results",
        },
        {"heading": "Risks", "question": "Acme risks 2022?", "route": "doc", "module": "risks"},
    ],
}


def _source(number: int, page: int, text: str) -> Source:
    return Source(number, "ACME_2022_10K", page, f"Acme 10-K 2022, page {page + 1}", text, 20)


@dataclass(frozen=True)
class Found:
    answer: Answer


class Specialist:
    """Answers each question with a scripted answer, recording what it was asked."""

    def __init__(self, answers: dict[str, Answer]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def answer(self, question: str) -> Found:
        self.asked.append(question)
        found = self.answers[question]
        if isinstance(found, Exception):
            raise found
        return Found(found)


def _answer(question: str, text: str, sources: Sequence[Source], cited: Sequence[int]) -> Answer:
    return Answer(question, True, text, "", list(sources), list(cited))


SHARED = _source(2, 40, "Risk factors: supply chain disruption and litigation.")
RESULTS = _answer(
    "Acme revenue 2022?",
    "Revenue was $10.0 billion in 2022 [1]. It rose 5% on higher prices [2].",
    [_source(1, 30, "Net sales 10.0 billion."), _source(2, 31, "Prices rose 5 percent.")],
    [1, 2],
)
RISKS = _answer(
    "Acme risks 2022?",
    "Acme names supply chain disruption as a risk [1]. It also faces litigation [1].",
    [SHARED.__class__(1, SHARED.doc_name, SHARED.page, SHARED.label, SHARED.text, 20)],
    [1],
)


def planner_and_editor(plan: object, summary: str) -> FakeLLM:
    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        if "plan research briefs" in messages[0]["content"]:
            return json.dumps(plan)
        return json.dumps({"summary": summary})

    return FakeLLM(reply)


def checker(verdicts: list[list[bool]]) -> FakeLLM:
    """A checker that answers each check with the next list of sentence verdicts."""
    queue = list(verdicts)

    def reply(messages: Sequence[Message], role: ModelRole) -> str:
        found = queue.pop(0)
        return json.dumps(
            {"sentences": [{"n": n, "supported": ok} for n, ok in enumerate(found, 1)]}
        )

    return FakeLLM(reply)


def test_parse_plan_keeps_at_most_five_sections_and_refuses_too_few() -> None:
    many = PLAN | {"sections": PLAN["sections"] * 4}

    assert len(brief.parse_plan(json.dumps(many)).sections) == brief.MAX_SECTIONS
    with pytest.raises(ValueError, match="fewer than 2"):
        brief.parse_plan(json.dumps(PLAN | {"sections": PLAN["sections"][:1]}))
    with pytest.raises(ValueError, match="No plan"):
        brief.parse_plan("I would start with the results.")


def test_make_plan_falls_back_to_the_request_as_one_section() -> None:
    plan, planned = brief.make_plan(FakeLLM(["no JSON here"]), "Write a brief on Acme.")

    assert not planned
    assert [s.question for s in plan.sections] == ["Write a brief on Acme."]
    assert plan.sections[0].route == "hybrid"


def test_plan_messages_list_every_module() -> None:
    prompt = brief.plan_messages("Brief on Acme")[0]["content"]

    assert all(f"- {name}:" in prompt for name in brief.MODULES)
    assert "2 to 5 sections" in prompt


def test_renumber_maps_citations_and_drops_unknown_ones() -> None:
    assert brief.renumber("A [1]. B [2][3].", {1: 4, 2: 5}) == "A [4]. B [5]."


def test_merge_sources_numbers_a_shared_page_once() -> None:
    first = brief.Section(brief.SectionPlan(heading="A", question="a"), RISKS)
    second = brief.Section(
        brief.SectionPlan(heading="B", question="b"),
        _answer(
            "b",
            "Same page [3].",
            [SHARED.__class__(3, SHARED.doc_name, SHARED.page, SHARED.label, SHARED.text, 20)],
            [3],
        ),
    )

    sources, maps = brief.merge_sources([first, second])

    assert [s.number for s in sources] == [1]
    assert maps == [{1: 1}, {3: 1}]


def test_the_crew_writes_checked_sections_and_a_summary_with_one_source_list() -> None:
    hybrid = Specialist({"Acme revenue 2022?": RESULTS})
    doc = Specialist({"Acme risks 2022?": RISKS})
    llm = planner_and_editor(
        PLAN, "Revenue rose 5% to $10.0 billion [1][2]. Litigation is a risk [3]."
    )
    check = checker([[True, False], [True, True], [True, True]])  # results, risks, summary
    events: list[tuple[str, dict[str, object]]] = []
    crew = brief.BriefCrew(doc, hybrid, llm, llm, check, workers=1)

    result = crew.run(
        "Write a brief on Acme's 2022.", lambda name, **data: events.append((name, data))
    )

    assert result.planned
    assert [s.answered for s in result.sections] == [True, True]
    assert result.sections[0].dropped == ["It rose 5% on higher prices [2]."]
    assert result.texts == [
        "Revenue was $10.0 billion in 2022 [1].",
        RISKS.text.replace("[1]", "[2]"),
    ]
    assert [s.number for s in result.sources] == [1, 2]  # the cut sentence's page is gone
    assert result.summary.startswith("Revenue rose 5%")
    markdown = result.markdown()
    assert markdown.startswith("# Acme in fiscal 2022")
    assert "## Results" in markdown
    assert "## Risks" in markdown
    assert [c["number"] for c in result.citations] == [1, 2]
    assert [name for name, _ in events] == ["plan", "section", "section", "edit"]


def test_a_section_without_support_is_named_as_not_covered() -> None:
    unanswerable = Answer("Acme risks 2022?", False, "", "the risk factors", [], [])
    crew = brief.BriefCrew(
        Specialist({"Acme risks 2022?": unanswerable}),
        Specialist({"Acme revenue 2022?": RESULTS}),
        planner_and_editor(PLAN, "Revenue was $10.0 billion [1]."),
        planner_and_editor(PLAN, "Revenue was $10.0 billion [1]."),
        workers=2,
    )

    result = crew.run("Write a brief on Acme's 2022.")

    assert result.missing == ["Risks"]
    assert "Not covered" in result.markdown()
    assert len(result.answered) == 1


def test_a_rate_limit_stops_a_strict_crew_and_empties_a_section_otherwise() -> None:
    limited = LLMError("429", rate_limited=True)
    specialists = (
        Specialist({"Acme risks 2022?": limited}),  # type: ignore[dict-item]
        Specialist({"Acme revenue 2022?": RESULTS}),
    )
    llm = planner_and_editor(PLAN, "Revenue was $10.0 billion [1].")

    with pytest.raises(LLMError):
        brief.BriefCrew(*specialists, llm, llm, strict=True, workers=1).run("Brief on Acme")
    result = brief.BriefCrew(*specialists, llm, llm, workers=1).run("Brief on Acme")
    assert result.sections[1].error == "429"
    assert result.missing == ["Risks"]
