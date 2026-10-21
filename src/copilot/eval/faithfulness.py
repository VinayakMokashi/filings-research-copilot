"""Faithfulness: is each sentence of an answer supported by the sources it cites? (step 3.7)

Correctness asks whether an answer matches the reference. Faithfulness asks something the
reference can't: whether the answer says only what its cited pages say. A correct figure
the model remembered, cited to a page that doesn't contain it, is correct and unfaithful;
a faithful answer can still be wrong when the cited page is the wrong one.

- The answer is split into sentences, each with the sources it cites. Citations after a
  sentence's full stop ("... points. [2] The ...") belong to that sentence.
- One judge call per answer checks every cited sentence against its cited pages only,
  with the calculator's expressions, so a computed figure counts as supported when its
  inputs are on the cited pages. The judge also names which cited sources contribute,
  which gives citation precision (Gao et al., 2023).
- Sentences that cite nothing aren't sent to the judge; they count as unsupported.
- A reply that can't be parsed marks every cited sentence unsupported, with the error
  recorded, so a judge failure never flatters the agent.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.answer.generate import citations
from copilot.llm import LLMClient, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

PROMPT_VERSION = "1"
ROLE: ModelRole = "fast"

SYSTEM_PROMPT = """\
You check whether each sentence of an answer is supported by the sources it cites. The \
sources are numbered pages from companies' SEC filings and earnings releases.

- A sentence is supported when its cited sources, read together, state what it says. \
Paraphrase, rounding and units written differently are fine.
- A computed figure is supported when the calculation listed for it uses figures that \
its cited sources state.
- A conclusion or judgement is supported when the facts it rests on are in its cited \
sources and it follows from them.
- Anything a sentence adds that its cited sources don't state makes it unsupported, even \
if it is true.

For each sentence, also list which of its cited sources contribute to it.

Return only a JSON object: {"sentences": [{"n": 1, "supported": true or false, \
"supporting": [source numbers]}, ...]}, one entry per sentence, in order."""

# A sentence ends at ".", "!" or "?" plus any citations after it, before whitespace and a
# capital letter (or the end). Decimal points are followed by digits, so they never match.
_END = re.compile(
    r"[.!?](?:\s*\[\d+(?:\s*,\s*\d+)*\])*(?=\s+[A-Z(\"'\N{LEFT DOUBLE QUOTATION MARK}]|\s*$)"
)
# A full stop after these is an abbreviation, not the end of a sentence.
_ABBREVIATION = re.compile(r"(?:\b[A-Z]|\b(?:Inc|Corp|Co|Ltd|No|vs|approx|e\.g|i\.e))$")


@dataclass(frozen=True, slots=True)
class Sentence:
    text: str
    cited: list[int]


@dataclass(frozen=True, slots=True)
class SentenceCheck:
    """One sentence and the verdict on it; `supported` is None when it cites nothing."""

    text: str
    cited: list[int]
    supported: bool | None
    supporting: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Faithfulness:
    """The sentence checks for one answer, and what they cost."""

    checks: list[SentenceCheck]
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None

    @property
    def cited_sentences(self) -> int:
        return sum(check.supported is not None for check in self.checks)

    @property
    def supported_sentences(self) -> int:
        return sum(check.supported is True for check in self.checks)

    @property
    def citations(self) -> int:
        return sum(len(check.cited) for check in self.checks)

    @property
    def supporting_citations(self) -> int:
        return sum(len(set(check.supporting) & set(check.cited)) for check in self.checks)

    @property
    def faithful(self) -> bool:
        """Every sentence cites a source and is supported by what it cites."""
        return bool(self.checks) and all(check.supported is True for check in self.checks)


class _Entry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    n: int
    supported: bool
    supporting: list[int] = Field(default_factory=list)


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentences: list[_Entry]


def sentences(text: str, valid: Sequence[int] | None = None) -> list[Sentence]:
    """The sentences of an answer, each with the source numbers it cites (in `valid`)."""
    pieces: list[str] = []
    start = 0
    for match in _END.finditer(text):
        if _ABBREVIATION.search(text[start : match.start()]):
            continue
        pieces.append(text[start : match.end()])
        start = match.end()
    pieces.append(text[start:])
    found = []
    for piece in pieces:
        piece = piece.strip()
        if piece:
            cited = [n for n in citations(piece) if valid is None or n in valid]
            found.append(Sentence(piece, cited))
    return found


def faithfulness_messages(
    checked: Sequence[Sentence],
    sources: Mapping[int, tuple[str, str]],
    calculations: Sequence[tuple[str, str, float | None]] = (),
) -> list[Message]:
    """The judge prompt: the cited sources, the calculations, and the sentences to check."""
    blocks = "\n\n".join(f"[{n}] {label}\n{text}" for n, (label, text) in sorted(sources.items()))
    lines = [f"Sources:\n\n{blocks}"]
    done = [(expression, value) for _, expression, value in calculations if value is not None]
    if done:
        listed = "\n".join(f"- {expression} = {value:,.4g}" for expression, value in done)
        lines.append(f"Calculations behind the answer's computed figures:\n{listed}")
    numbered = "\n".join(
        f"{number}. {sentence.text} (cites {', '.join(map(str, sentence.cited))})"
        for number, sentence in enumerate(checked, start=1)
    )
    lines.append(f"Sentences:\n{numbered}")
    return [system(SYSTEM_PROMPT), user("\n\n".join(lines))]


def parse_reply(text: str) -> _Reply:
    try:
        return _Reply.model_validate(json_object(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"The reply isn't a valid sentence check: {exc}") from exc


def check(
    llm: LLMClient,
    text: str,
    sources: Mapping[int, tuple[str, str]],
    calculations: Sequence[tuple[str, str, float | None]] = (),
    *,
    role: ModelRole = ROLE,
) -> Faithfulness:
    """Check each sentence of `text` against the sources (number to label and text) it cites."""
    parts = sentences(text, valid=list(sources))
    checked = [sentence for sentence in parts if sentence.cited]
    if not checked:
        return Faithfulness([SentenceCheck(s.text, [], None) for s in parts])
    cited = {n: sources[n] for sentence in checked for n in sentence.cited}
    response = llm.complete(
        faithfulness_messages(checked, cited, calculations),
        role=role,
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    try:
        verdicts = {entry.n: entry for entry in parse_reply(response.text).sentences}
        error = None
    except ValueError as exc:
        verdicts, error = {}, str(exc)
    checks = []
    number = 0
    for sentence in parts:
        if not sentence.cited:
            checks.append(SentenceCheck(sentence.text, [], None))
            continue
        number += 1
        entry = verdicts.get(number)
        supported = entry.supported if entry is not None else False
        supporting = [n for n in entry.supporting if n in sentence.cited] if entry else []
        checks.append(SentenceCheck(sentence.text, sentence.cited, supported, supporting))
    return Faithfulness(
        checks,
        model=response.model,
        prompt_tokens=response.prompt_tokens or 0,
        completion_tokens=response.completion_tokens or 0,
        error=error,
    )
