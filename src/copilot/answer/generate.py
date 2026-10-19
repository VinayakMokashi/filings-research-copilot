"""Grounded generation: an answer built only from numbered sources, with citations (step 3.4).

The answer model sees the question and the numbered sources, and must return JSON:

    {"answerable": true,
     "answer": "3M's capital expenditure was $1,577 million in fiscal 2018 [2], or {c1}% of
                net sales [2][3].",
     "calculations": [{"id": "c1", "expression": "1577 / 32765 * 100", "decimals": 1}],
     "missing": ""}

- **Citations.** Every factual sentence cites the sources that state it, as [n]. Some models
  write 【n】 instead, a habit from their browsing tools; those are rewritten as [n].
  Citations to numbers that aren't sources are left out of the cited sources and recorded.
- **Arithmetic.** The model never computes a number itself: it writes the expression, the
  calculator (`copilot.answer.calculator`) evaluates it, and the result replaces `{c1}`.
- **Abstention.** If the sources don't contain what the question needs, the model sets
  `answerable` to false and says what is missing, instead of guessing.

The reply is parsed leniently (code fences and surrounding prose are ignored) and checked
against a schema; a reply that can't be parsed becomes an unanswerable answer with the error
recorded, never an exception.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.answer.calculator import Calculation, run
from copilot.answer.context import Source
from copilot.llm import LLMClient, LLMResponse, Message, ModelRole, system, user

PROMPT_VERSION = "2"
ROLE: ModelRole = "strong"

SYSTEM_PROMPT = """\
You answer questions about public companies using only the numbered sources provided, \
which are pages from the companies' SEC filings and earnings releases.

Rules:
- Use only facts the sources state. Don't use outside knowledge, even when you are sure of it.
- End every sentence that states a fact with the numbers of the sources that state it, in \
square brackets, like [2] or [2][5]. An answer without citations is not accepted.
- Don't do arithmetic yourself. When the answer needs a computed number (a ratio, total, \
difference, growth rate or average), add an expression to "calculations" that uses only \
numbers from the sources with + - * / and parentheses, give it an id such as c1 and the \
number of decimals to show, and write {c1} in the answer where the result goes.
- If the sources don't contain what the question needs, set "answerable" to false and name \
in "missing" the facts that are missing, with their line items and periods, such as \
"capital expenditure for fiscal 2017".
- When the question asks for a judgement, such as whether a margin is healthy, give it with \
the figures it rests on.
- Answer in at most four sentences, and give the units and fiscal period of every figure.

Return only a JSON object with the keys "answerable" (true or false), "answer" (text whose \
every sentence ends with its citations), "calculations" (a list of objects with "id", \
"expression" and "decimals") and "missing" (text, empty when nothing is missing)."""


class _CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    expression: str
    decimals: int = Field(default=2, ge=0, le=6)


class _Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answerable: bool
    answer: str = ""
    calculations: list[_CalculationRequest] = Field(default_factory=list)
    missing: str = ""


@dataclass(frozen=True, slots=True)
class Answer:
    """One answer, with what it rests on and what it cost."""

    question: str
    answerable: bool
    text: str
    missing: str
    sources: list[Source]
    cited: list[int]
    invalid_citations: list[int] = field(default_factory=list)
    calculations: list[Calculation] = field(default_factory=list)
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None

    @property
    def cited_sources(self) -> list[Source]:
        by_number = {source.number: source for source in self.sources}
        return [by_number[number] for number in self.cited if number in by_number]


def answer_messages(question: str, sources: Sequence[Source]) -> list[Message]:
    blocks = "\n\n".join(f"[{s.number}] {s.label}\n{s.text}" for s in sources)
    return [system(SYSTEM_PROMPT), user(f"Question: {question}\n\nSources:\n\n{blocks}")]


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_LENTICULAR = re.compile(
    r"\N{LEFT BLACK LENTICULAR BRACKET}\s*(\d+(?:\s*,\s*\d+)*)\s*"
    r"(?:\N{DAGGER}[^\N{RIGHT BLACK LENTICULAR BRACKET}]*)?\N{RIGHT BLACK LENTICULAR BRACKET}"
)
_PLACEHOLDER = re.compile(r"\{\s*(c\d+)\s*\}")


def parse_draft(text: str) -> _Draft:
    """The JSON object in a model reply, checked against the schema."""
    body = _FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The reply has no JSON object.")
    try:
        return _Draft.model_validate(json.loads(body[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"The reply isn't a valid answer object: {exc}") from exc


def fill(text: str, calculations: Sequence[Calculation]) -> str:
    """The answer with each {cN} replaced by its computed value."""
    by_id = {calculation.id: calculation for calculation in calculations}

    def replace(match: re.Match[str]) -> str:
        calculation = by_id.get(match.group(1))
        return calculation.text if calculation is not None else "[calculation missing]"

    return _PLACEHOLDER.sub(replace, text)


def normalise_citations(text: str) -> str:
    """Citations written as 【2】 or 【2†L4-L9】 rewritten as [2]."""
    return _LENTICULAR.sub(lambda match: f"[{match.group(1)}]", text)


def citations(text: str) -> list[int]:
    """Source numbers cited in the text, in order of first appearance."""
    numbers: list[int] = []
    for match in _CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part)
            if number not in numbers:
                numbers.append(number)
    return numbers


def build_answer(question: str, sources: Sequence[Source], response: LLMResponse) -> Answer:
    """The parsed, calculated and checked answer from one model reply."""
    model = response.model
    prompt_tokens = response.prompt_tokens or 0
    completion_tokens = response.completion_tokens or 0
    try:
        draft = parse_draft(response.text)
    except ValueError as exc:
        return Answer(
            question=question,
            answerable=False,
            text="",
            missing="",
            sources=list(sources),
            cited=[],
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=response.latency_s,
            error=str(exc),
        )
    calculations = [run(c.id, c.expression, c.decimals) for c in draft.calculations]
    text = normalise_citations(fill(draft.answer, calculations))
    numbers = {source.number for source in sources}
    cited = citations(text)
    return Answer(
        question=question,
        answerable=draft.answerable,
        text=text,
        missing=draft.missing,
        sources=list(sources),
        cited=[number for number in cited if number in numbers],
        invalid_citations=[number for number in cited if number not in numbers],
        calculations=calculations,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_s=response.latency_s,
    )


def generate(llm: LLMClient, question: str, sources: Sequence[Source]) -> Answer:
    response = llm.complete(
        answer_messages(question, sources),
        role=ROLE,
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    return build_answer(question, sources, response)
