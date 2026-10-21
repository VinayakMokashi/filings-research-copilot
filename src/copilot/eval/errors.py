"""Error analysis: why an answer that isn't correct went wrong (step 3.7).

Each answer that the judge didn't mark correct gets one category, from the first rule that
applies, using only what the run recorded:

1. **Refused, evidence retrieved**: the agent said its sources lack the answer although an
   evidence page was among them. The model missed what was there.
2. **Refused, evidence not retrieved**: a refusal with no evidence page in the context;
   retrieval failed, and refusing was the honest outcome.
3. **Calculation broke**: a calculation failed or a placeholder was left unfilled, so the
   figure the answer needed never reached it.
4. **Evidence not retrieved**: a wrong answer with no evidence page in the context. Other
   pages can hold the same figures, so this points at retrieval but doesn't prove it.
5. **Wrong with the evidence in context**: the evidence was there and the answer is still
   wrong: a misread figure, the wrong period or definition, or an incomplete answer.

The categories are a first sort. Reading the answers in the last group against their
sources splits it further.
"""

from __future__ import annotations

import re

CATEGORIES = (
    "correct",
    "refused, evidence retrieved",
    "refused, evidence not retrieved",
    "calculation broke",
    "evidence not retrieved",
    "wrong with the evidence in context",
)

# A placeholder the calculator didn't fill: "{c1}" or "{c1*100}".
_PLACEHOLDER = re.compile(r"\{\s*c\d+[^}]*\}|\[calculation (?:failed|missing)\]")


def unfilled(text: str) -> bool:
    """Whether the answer still shows a calculation placeholder or a calculation failure."""
    return bool(_PLACEHOLDER.search(text))


def categorise(outcome: str, *, context_hit: bool, calculation_failed: bool, text: str = "") -> str:
    """The category of one answer; see the module docstring for the rules."""
    if outcome == "correct":
        return "correct"
    if outcome == "refused":
        return "refused, evidence retrieved" if context_hit else "refused, evidence not retrieved"
    if calculation_failed or unfilled(text):
        return "calculation broke"
    if not context_hit:
        return "evidence not retrieved"
    return "wrong with the evidence in context"
