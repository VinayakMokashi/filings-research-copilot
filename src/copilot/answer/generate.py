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

import dataclasses
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.answer.calculator import Calculation, run_all
from copilot.answer.context import Source
from copilot.llm import LLMClient, LLMResponse, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

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


_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_LENTICULAR = re.compile(
    r"\N{LEFT BLACK LENTICULAR BRACKET}\s*(\d+(?:\s*,\s*\d+)*)\s*"
    r"(?:\N{DAGGER}[^\N{RIGHT BLACK LENTICULAR BRACKET}]*)?\N{RIGHT BLACK LENTICULAR BRACKET}"
)
# "{c1}", or "{c1*100:.1f}": models sometimes scale a result in the placeholder itself, or
# add a Python format code giving the decimals.
_PLACEHOLDER = re.compile(
    r"\{\s*(c\d+)\s*(?:([*/+-])\s*(\d+(?:\.\d+)?)\s*)?(?::\s*,?\.(\d)f\s*)?\}"
)
_OPERATIONS: dict[str, Callable[[float, float], float | None]] = {
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b else None,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
}
_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
# A number as an answer writes it, with an optional scale word: "$1.577 billion", "122 million".
_WRITTEN = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:\s*(thousand|million|billion|trillion)\b)?", re.IGNORECASE
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Words that already say a figure fell, so its value is shown without a minus sign.
_FALL = re.compile(
    r"\b(?:fell|fall|falls|dropped|drop|declined|decline|decreased|decrease|down|lower)"
    r"(?:\s+(?:by|of))?\s*\$?\s*$",
    re.IGNORECASE,
)
_SCALE_AFTER = re.compile(r"\s*(?:thousand|million|billion|trillion)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?](?:\[\d+\])*\s+(?=[A-Z])")
_LOOKBACK = 160  # characters before a placeholder searched for the model's own copy of it
_TOLERANCE = 0.005


def parse_draft(text: str) -> _Draft:
    """The JSON object in a model reply, checked against the schema."""
    try:
        return _Draft.model_validate(json_object(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"The reply isn't a valid answer object: {exc}") from exc


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOLERANCE * max(abs(a), abs(b))


def _sentence_before(text: str, index: int) -> str:
    """The part of the placeholder's sentence that comes before it, at most _LOOKBACK long."""
    window = text[max(0, index - _LOOKBACK) : index]
    ends = list(_SENTENCE_END.finditer(window))
    return window[ends[-1].end() :] if ends else window


def numbers_in(text: str) -> list[float]:
    """Every number in a text, commas removed: "1,577 / 32,765" gives 1577 and 32765."""
    return [float(number.replace(",", "")) for number in _NUMBER.findall(text)]


def _written_out(value: float, before: str, expression: str) -> bool:
    """Whether the sentence already states `value` as a number of the model's own.

    A written number counts with or without its scale word, since the calculator works in
    the units of the source ("$7,737,590 thousand" and 7,737,590). Years don't count, nor do
    the expression's operands, so "from $100 million to $200 million, an increase of {c1}"
    keeps its computed $100 million; nor do results under 1,000, which collide by chance.
    """
    if abs(value) < 1000:
        return False
    operands = numbers_in(expression)
    for match in _WRITTEN.finditer(before):
        digits, scale = float(match.group(1).replace(",", "")), match.group(2)
        if scale is None and digits.is_integer() and 1900 <= digits <= 2100:
            continue
        readings = [digits, digits * _SCALES[scale.lower()]] if scale else [digits]
        for written in readings:
            if _close(written, abs(value)) and not any(_close(written, op) for op in operands):
                return True
    return False


def _compact(value: float) -> str:
    """A value of a million or more in millions, billions or trillions: "5.186 billion"."""
    for word, size in (("trillion", 1e12), ("billion", 1e9), ("million", 1e6)):
        if abs(value) >= size:
            return f"{value / size:,.3f}".rstrip("0").rstrip(".") + f" {word}"
    return f"{value:,}"


def _in_raw_units(expression: str, raw: Sequence[float]) -> bool:
    """Whether every operand is one of the numbers a source states in raw units."""
    operands = numbers_in(expression)
    return bool(operands) and all(any(_close(op, number) for number in raw) for op in operands)


def _drop_repeats(text: str, by_id: dict[str, Calculation]) -> str:
    """The text without placeholders whose result the model already wrote out itself."""
    for match in reversed(list(_PLACEHOLDER.finditer(text))):
        calculation = by_id.get(match.group(1))
        if calculation is None or calculation.value is None or match.group(2) is not None:
            continue
        before = _sentence_before(text, match.start())
        if not _written_out(calculation.value, before, calculation.expression):
            continue
        start, end = match.start(), match.end()
        if text[start - 1 : start] == "(" and text[end : end + 1] == ")":
            start, end = start - 1, end + 1
        while start > 0 and text[start - 1] == " ":
            start -= 1
        text = text[:start] + text[end:]
    return text


def fill(text: str, calculations: Sequence[Calculation], raw: Sequence[float] = ()) -> str:
    """The answer with each {cN} (or {cN*100}, and so on) replaced by its computed value.

    Three rules keep a computed figure readable where it lands. A result the model has
    already written out itself, earlier in the same sentence, isn't repeated. A negative
    result after words that already say it fell ("fell by", "a decline of") loses its minus
    sign. And a result of a million or more, computed only from `raw`, the numbers a source
    states in raw units (the facts database's dollars), is written in millions, billions or
    trillions unless a scale word follows; a filing's tables are often in thousands or
    millions, so a result from their numbers keeps the units the text gives it.
    """
    by_id = {calculation.id: calculation for calculation in calculations}
    text = _drop_repeats(text, by_id)

    def replace(match: re.Match[str]) -> str:
        calculation = by_id.get(match.group(1))
        if calculation is None:
            return "[calculation missing]"
        operator, operand, decimals = match.group(2), match.group(3), match.group(4)
        if decimals is not None:
            calculation = dataclasses.replace(calculation, decimals=int(decimals))
        if calculation.value is None:
            return calculation.text
        value: float | None = calculation.value
        if operator is not None:
            value = _OPERATIONS[operator](calculation.value, float(operand))
        if value is None:
            return dataclasses.replace(calculation, value=None).text
        if value < 0 and _FALL.search(_sentence_before(text, match.start())):
            value = -value
        if (
            abs(value) >= 1e6
            and operator is None
            and _in_raw_units(calculation.expression, raw)
            and not _SCALE_AFTER.match(text, match.end())
        ):
            return _compact(value)
        return dataclasses.replace(calculation, value=value).text

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
    calculations = run_all([(c.id, c.expression, c.decimals) for c in draft.calculations])
    # The facts database's source (page -1, not a filing's page) gives values in dollars.
    raw = [number for source in sources if source.page < 0 for number in numbers_in(source.text)]
    text = normalise_citations(fill(draft.answer, calculations, raw))
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
