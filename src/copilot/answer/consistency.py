"""Self-consistency for figure answers: sample several, keep the figure most of them give.

A model asked the same question several times, sampling at a non-zero temperature, may
reach different figures: one reads the wrong line of a table, another adds a column the
others don't. Self-consistency (Wang et al., 2023) samples several answers and keeps the
one most of them agree on, which helps when the errors are scattered and the right answer
is the common one.

Here the answers are grouped by their main figure, the first one each gives (figures that
differ only in scale, such as $1,577 million and $1.577 billion, are one figure, within 1%,
as the answer judge compares them). Refusals form a group of their own, and so do answers
without a figure. The largest group wins; on a tie, the group with the earliest answer, so
with the deterministic answer first, a split vote keeps it.

The cost grows with the samples: each one is a full answer call over the same sources.
"""

from __future__ import annotations

from collections.abc import Sequence

from copilot.answer.context import Source
from copilot.answer.generate import ROLE, Answer, answer_messages, build_answer
from copilot.eval.judge import Figure, distance, figures, strip_citations
from copilot.llm import LLMClient

TOLERANCE = 0.01
TEMPERATURE = 0.7


def sample(
    llm: LLMClient,
    question: str,
    sources: Sequence[Source],
    seed: int,
    temperature: float = TEMPERATURE,
) -> Answer:
    """One sampled answer; `seed` tells samples apart (and keys them apart in a cache)."""
    response = llm.complete(
        answer_messages(question, sources),
        role=ROLE,
        temperature=temperature,
        max_tokens=4096,
        response_format={"type": "json_object"},
        seed=seed,
    )
    return build_answer(question, sources, response)


def key_figure(answer: Answer) -> Figure | None:
    """The answer's main figure: the first it gives, or None for a refusal or no figure."""
    if not answer.answerable:
        return None
    found = figures(strip_citations(answer.text))
    return found[0] if found else None


def _same(a: Answer, b: Answer, tolerance: float) -> bool:
    if a.answerable != b.answerable:
        return False
    first, second = key_figure(a), key_figure(b)
    if first is None or second is None:
        return first is None and second is None
    return distance(first, second) <= tolerance


def vote(answers: Sequence[Answer], tolerance: float = TOLERANCE) -> tuple[int, float]:
    """The position of the answer to keep, and the share of answers that agree with it."""
    if not answers:
        raise ValueError("No answers to vote on.")
    groups: list[list[int]] = []
    for position, answer in enumerate(answers):
        for group in groups:
            if _same(answers[group[0]], answer, tolerance):
                group.append(position)
                break
        else:
            groups.append([position])
    best = max(groups, key=lambda group: (len(group), -group[0]))
    return best[0], len(best) / len(answers)
