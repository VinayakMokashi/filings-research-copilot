"""The brief set and its rubrics (step 7.6): what each brief must cover, graded by a judge.

A brief can't be scored against one reference answer: two good briefs on the same filing
choose different figures and words. Each request in `eval/briefs/briefs.jsonl` comes with
a rubric instead, four or five items that name what the request asks for ("States 3M's
total net sales for 2022, with a figure"; "Discusses 3M's litigation exposure"). A judge
reads the brief and says which items it covers. It doesn't decide whether the facts are
right: the faithfulness check does that, sentence by sentence, against the sources each
sentence cites.

The judge runs on the `fast` role, the evaluation's judge model (ADR-0014), which writes
none of the briefs; `grade` takes the role, so a second judge can grade the same briefs
for a jury.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.llm import LLMClient, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

BRIEFS = Path("eval/briefs/briefs.jsonl")
JUDGE_ROLE: ModelRole = "fast"
PROMPT_VERSION = "1"

RUBRIC_PROMPT = """\
You grade research briefs against a checklist. For each numbered item, decide whether the \
brief covers it: true only when the brief states what the item asks for, such as a figure \
when the item asks for one, or a named matter when it names one. A passing mention that \
leaves out what the item asks for is false. Don't judge whether the brief's facts are \
correct, only whether it covers the item.

Return only a JSON object with the key "items": a list with one object for each item, in \
order, with the keys "n" (the item's number), "met" (true or false) and "reason" (one \
short sentence)."""


class BriefCase(BaseModel):
    """One request of the brief set, with its rubric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    company: str
    filing: str
    request: str
    rubric: list[str] = Field(min_length=1)


def load_briefs(path: Path = BRIEFS) -> list[BriefCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [BriefCase.model_validate(json.loads(line)) for line in lines if line.strip()]


class _Item(BaseModel):
    model_config = ConfigDict(extra="ignore")

    n: int
    met: bool
    reason: str = ""


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[_Item]


@dataclass(frozen=True, slots=True)
class RubricGrade:
    """Which rubric items a brief covers, by the judge's reading, and why."""

    met: list[bool]
    reasons: list[str]
    model: str = ""
    error: str | None = None

    @property
    def score(self) -> float:
        """The share of the rubric's items the brief covers."""
        return sum(self.met) / len(self.met) if self.met else 0.0


def rubric_messages(case: BriefCase, text: str) -> list[Message]:
    items = "\n".join(f"{n}. {item}" for n, item in enumerate(case.rubric, start=1))
    return [
        system(RUBRIC_PROMPT),
        user(f"Request: {case.request}\n\nChecklist:\n{items}\n\nBrief:\n{text}"),
    ]


def parse_grade(text: str, items: int) -> tuple[list[bool], list[str]]:
    """Each item's verdict from a judge's reply; an item it doesn't mention isn't met.

    ValueError when the reply holds no verdicts.
    """
    try:
        reply = _Reply.model_validate(json_object(text))
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"The reply isn't a rubric grade: {exc}") from exc
    by_number = {item.n: item for item in reply.items}
    met = [bool(by_number[n].met) if n in by_number else False for n in range(1, items + 1)]
    reasons = [by_number[n].reason if n in by_number else "" for n in range(1, items + 1)]
    return met, reasons


def grade(llm: LLMClient, case: BriefCase, text: str, role: ModelRole = JUDGE_ROLE) -> RubricGrade:
    """The judge's reading of which of the case's rubric items `text` covers."""
    if not text.strip():
        return RubricGrade([False] * len(case.rubric), [""] * len(case.rubric))
    response = llm.complete(
        rubric_messages(case, text),
        role=role,
        temperature=0.0,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    try:
        met, reasons = parse_grade(response.text, len(case.rubric))
    except ValueError as exc:
        empty = [False] * len(case.rubric)
        return RubricGrade(empty, [""] * len(case.rubric), response.model, str(exc)[:300])
    return RubricGrade(met, reasons, response.model)


def agreement(first: Sequence[bool], second: Sequence[bool]) -> float:
    """The share of items two judges graded alike."""
    if len(first) != len(second) or not first:
        raise ValueError("Two gradings of the same items are needed.")
    return sum(a == b for a, b in zip(first, second, strict=True)) / len(first)
