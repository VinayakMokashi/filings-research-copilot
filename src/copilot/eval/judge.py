"""An LLM judge for answer correctness against FinanceBench's reference answers (step 3.6).

FinanceBench gives each question a reference answer written by a financial analyst: a bare
figure in the units the question names ("$1577.00" for USD millions), a yes or no with its
reasons, or a few sentences. A string match fails on every rounding and unit difference,
so a model compares each answer with the reference, and a sample of its verdicts is
checked against reference labels before its numbers are trusted.

- **Three outcomes**, as in the FinanceBench paper: correct, incorrect, or refused. A
  refusal (the agent said its sources don't contain the answer) needs no judge.
- **A different model family.** Models tend to rate text like their own more highly, so
  the default judge is the fast role's model, not the one that wrote the answers.
- **Tolerance.** Numbers match when they are equal at the reference's precision or within
  1%; units and notation may differ. Judgements must reach the same conclusion, and a
  figure the answer gives for something the reference also quantifies must match too: for
  an analyst, a wrong figure under the right conclusion is still an error.
- **Arithmetic in code.** Models misjudge "within 1%" (one called 8.738 and 8.70 more than
  1% apart), so `closest_figures` pairs each figure in the reference with the nearest
  figure in the answer, allowing for thousands, millions and billions, and the judge gets
  the computed distances.
- **Citations are removed** before judging: without the sources, "[2]" means nothing.
- The reply is one JSON object with the verdict and a short reason. A reply that can't be
  parsed counts as incorrect, with the error recorded, so a judge failure never flatters
  the system.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from copilot.llm import LLMClient, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

PROMPT_VERSION = "2"
ROLE: ModelRole = "fast"

Verdict = Literal["correct", "incorrect", "refused"]

RUBRIC = """\
The candidate answer is correct when it gives the same figure, fact or conclusion as the \
reference:
- Numbers match when they are equal after rounding to the precision the reference uses, \
or within 1% of each other.
- Units and notation can differ. Read the question for the units the reference uses: if it \
asks for USD millions, "$1577.00" means $1,577 million, the same as $1.577 billion. 0.25 \
and 25% are the same.
- For yes-or-no questions and judgements, the conclusion must match. The reasons may \
differ, but a figure the candidate gives for something the reference also quantifies \
must match it, even if the candidate used another reasonable definition.
- When the question asks for several figures or parts, each one must match.
- Extra detail is fine unless it contradicts the reference.

The candidate answer is incorrect when a figure or conclusion differs from the reference, \
when it hedges between answers, or when it doesn't answer the question."""

SYSTEM_PROMPT = f"""\
You check answers to questions about public companies' financial filings against a \
reference answer written by a financial analyst.

{RUBRIC}

Judge only against the reference, not against your own knowledge of the company. After the \
candidate answer you get computed comparisons: for each figure in the reference, the \
closest figure in the candidate and how far apart they are, allowing for thousands, \
millions and billions. Use those distances for the 1% rule instead of your own arithmetic; \
whether the two figures measure the same thing is for you to decide.

Return only a JSON object: {{"verdict": "correct" or "incorrect", "reason": "one short \
sentence"}}."""

_CITATIONS = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")
# A figure: digits with optional thousands separators and decimals, then an optional "x"
# (times) and percent sign. Not part of a word or a short year, so "FY2022", "Q3", "3M"
# and "Jun'23" hold no figures.
_FIGURE = re.compile(
    r"(?<![\w.'\N{RIGHT SINGLE QUOTATION MARK}])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?:x\b)?(?!\w)\s*(%|percent\b)?"
)
MAX_FIGURES = 6
# Each power of a thousand between a billionth and a billion: units, thousands, millions.
_SCALES = tuple(1000.0**k for k in range(-3, 4))


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdict: Literal["correct", "incorrect"]
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Judgement:
    """One verdict, why, and what it cost."""

    verdict: Verdict
    reason: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Figure:
    """A number as written in an answer, and its value (a percentage's value is unscaled)."""

    text: str
    value: float
    percent: bool


def strip_citations(text: str) -> str:
    return _CITATIONS.sub("", text).strip()


def figures(text: str) -> list[Figure]:
    """The figures in `text`, leaving out bare years (1990 to 2035) such as "in 2022"."""
    found = []
    for match in _FIGURE.finditer(text):
        digits, percent = match.group(1), bool(match.group(2))
        value = float(digits.replace(",", ""))
        if not percent and digits.isdigit() and 1990 <= value <= 2035:
            continue
        found.append(Figure(match.group(0).strip(), value, percent))
    return found


def distance(reference: Figure, candidate: Figure) -> float:
    """How far apart two figures are, relative to the reference, after allowing for scale.

    Plain numbers may differ by a power of a thousand ($1,577 million and 1.577 billion);
    a percentage may be written as a fraction (25% and 0.25).
    """
    if reference.value == 0 or candidate.value == 0:
        return 0.0 if reference.value == candidate.value else math.inf
    if reference.percent != candidate.percent:
        scales: tuple[float, ...] = (1.0, 100.0, 0.01)
    else:
        scales = (1.0,) if reference.percent else _SCALES
    return min(abs(candidate.value * scale / reference.value - 1.0) for scale in scales)


def closest_figures(reference: str, answer: str) -> list[tuple[Figure, Figure | None, float]]:
    """Each of the reference's first few figures, the answer's closest one and the distance."""
    candidates = figures(answer)
    pairs: list[tuple[Figure, Figure | None, float]] = []
    distinct = list({figure.text: figure for figure in figures(reference)}.values())
    for figure in distinct[:MAX_FIGURES]:
        if not candidates:
            pairs.append((figure, None, math.inf))
            continue
        best = min(candidates, key=lambda candidate: distance(figure, candidate))
        pairs.append((figure, best, distance(figure, best)))
    return pairs


def comparisons(reference: str, answer: str) -> str:
    """The computed comparisons the judge reads after the candidate answer."""
    pairs = closest_figures(reference, answer)
    if not pairs:
        return "Computed comparisons: the reference gives no figures."
    lines = []
    for figure, closest, apart in pairs:
        if closest is None:
            lines.append(f"- reference {figure.text}: the candidate gives no figures")
        else:
            lines.append(
                f"- reference {figure.text}, closest candidate figure {closest.text}: "
                f"{apart:.2%} apart"
            )
    return "Computed comparisons:\n" + "\n".join(lines)


def judge_messages(
    question: str, reference: str, answer: str, justification: str | None = None
) -> list[Message]:
    candidate = strip_citations(answer)
    parts = [f"Question: {question}", f"Reference answer: {reference}"]
    if justification and justification.strip():
        parts.append(f"How the reference was reached: {justification.strip()}")
    parts.append(f"Candidate answer: {candidate}")
    parts.append(comparisons(reference, candidate))
    return [system(SYSTEM_PROMPT), user("\n\n".join(parts))]


def parse_verdict(text: str) -> _Reply:
    """The verdict object in a judge reply, checked against the schema."""
    try:
        return _Reply.model_validate(json_object(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"The reply isn't a valid verdict: {exc}") from exc


def judge(
    llm: LLMClient,
    question: str,
    reference: str,
    answer: str,
    *,
    justification: str | None = None,
    answered: bool = True,
    role: ModelRole = ROLE,
) -> Judgement:
    """Compare `answer` with `reference`; a refusal or an empty answer needs no call."""
    if not answered or not strip_citations(answer):
        return Judgement("refused", "The agent said its sources don't contain the answer.")
    response = llm.complete(
        judge_messages(question, reference, answer, justification),
        role=role,
        temperature=0.0,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    model = response.model
    prompt_tokens = response.prompt_tokens or 0
    completion_tokens = response.completion_tokens or 0
    try:
        reply = parse_verdict(response.text)
    except ValueError as exc:
        return Judgement(
            "incorrect",
            "",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error=str(exc),
        )
    return Judgement(
        reply.verdict,
        reply.reason.strip(),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
