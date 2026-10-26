"""Instructions hidden in retrieved text, quoted out before a model reads them (step 6.2).

Retrieved filing pages go into the answer prompt as numbered sources. A page that told the
model what to do ("ignore your previous instructions and ...") would be an indirect prompt
injection (Greshake et al., 2023). SEC filings are unlikely to carry one, but nothing in a
retrieval pipeline vouches for what a page says, so before a page becomes a source, every
sentence that reads as an instruction to an assistant is replaced by a short notice. A page
with no such sentence passes through unchanged, so its prompt, and the cached answer to it,
stay the same.

The patterns aim at what injections say and filings don't: talk of an assistant's
instructions or prompt, the role markers of chat formats, and orders about how to reply.
The red-team set in eval/injection/ checks them, and `poe scan-injections` counts what they
flag in the parsed corpus.
"""

from __future__ import annotations

import re

NOTICE = "[Removed: text that read as an instruction to an assistant.]"

PATTERNS: dict[str, str] = {
    "ignore instructions": (
        r"\b(?:ignore|disregard|forget|override)\b[^.!?\n]{0,40}"
        r"\b(?:instructions?|prompts?|guidelines|guardrails)\b"
    ),
    "system prompt": r"\b(?:system|developer|hidden)\s+(?:prompt|instructions?)\b",
    "you are now": r"\byou\s+are\s+now\b|\byou\s+are\s+(?:an?\s+)?(?:ai|assistant|chatbot|llm)\b",
    "new instructions": r"\bnew\s+instructions?\s*:",
    "do not follow": r"\b(?:do\s+not|don't)\s+follow\s+(?:your|the|any)\s+(?:instructions|rules)\b",
    "respond only": r"\b(?:respond|reply|answer)\s+only\s+with\b",
    "chat markers": r"<\|?\s*(?:im_start|im_end|system|assistant)\s*\|?>|\[/?(?:INST|SYS)\]",
    "role label": r"(?m)^\s*(?:system|assistant)\s*:",
    "as an ai": r"\bas\s+an\s+ai(?:\s+language)?\s+model\b",
}
_COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()}
_BOUNDARY = re.compile(r"[.!?](?=\s|$)|\n")


def findings(text: str) -> list[tuple[str, int, int]]:
    """Each match as (pattern name, start, end), in the order found."""
    found = []
    for name, pattern in _COMPILED.items():
        found += [(name, match.start(), match.end()) for match in pattern.finditer(text)]
    return sorted(found, key=lambda item: item[1])


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    """The span of the sentence, or line, around [start, end)."""
    before = [m.end() for m in _BOUNDARY.finditer(text, 0, start)]
    after = _BOUNDARY.search(text, end)
    return (before[-1] if before else 0), (after.end() if after else len(text))


def neutralise(text: str) -> tuple[str, int]:
    """The text with every instruction-like sentence replaced by a notice, and how many."""
    spans: list[list[int]] = []
    for _, start, end in findings(text):
        first, last = _sentence(text, start, end)
        if spans and first <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], last)
        else:
            spans.append([first, last])
    if not spans:
        return text, 0
    pieces, cursor = [], 0
    for first, last in spans:
        lead = text[first:last][: len(text[first:last]) - len(text[first:last].lstrip())]
        pieces += [text[cursor:first], lead, NOTICE]
        cursor = last
    pieces.append(text[cursor:])
    return "".join(pieces), len(spans)
