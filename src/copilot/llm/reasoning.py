"""Separate a reasoning model's visible chain of thought from its final answer."""

from __future__ import annotations

import re

_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_OPEN = re.compile(r"<think>", re.IGNORECASE)
_CLOSE = re.compile(r"</think>", re.IGNORECASE)


def split_reasoning(text: str) -> tuple[str, str | None]:
    """Return `(answer, reasoning)` for a reply that may contain `<think>` blocks.

    Handles three shapes besides plain text:
    - complete `<think>...</think>` blocks anywhere in the reply;
    - a reply that starts inside the block, so only `</think>` appears;
    - a reply cut off while still reasoning, so `<think>` never closes.

    In the last two cases the unpaired part counts as reasoning, never as the answer,
    so a draft inside the reasoning can't be mistaken for the final output.
    """
    reasoning: list[str] = [part.strip() for part in _BLOCK.findall(text)]
    rest = _BLOCK.sub("", text)

    pieces = _CLOSE.split(rest)
    if len(pieces) > 1:
        reasoning.extend(piece.strip() for piece in pieces[:-1])
        rest = pieces[-1]

    head, *tail = _OPEN.split(rest, maxsplit=1)
    if tail:
        reasoning.append(tail[0].strip())
        rest = head

    joined = "\n\n".join(part for part in reasoning if part)
    return rest.strip(), joined or None
