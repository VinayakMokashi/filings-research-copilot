"""Query rewriting: search for what the question needs, not for how it was asked (step 3.2).

FinanceBench's questions often carry template instructions (how many decimal places to round
to, what to say if a metric doesn't suit the company) and name a metric without saying where
it is reported. Each rewrite is one model call, made through the cache:

- **multi-query**: three short search queries in the words a filing would use;
- **HyDE** (Gao et al., 2022): a short passage in the style of a filing that would answer
  the question, embedded as a passage rather than as a query;
- **decomposition**: the separate facts the answer needs, one query each (a ratio needs its
  numerator and its denominator, a change needs both periods).

`expand` returns the searches to run: the original question first, then the rewrites. The
caller searches each within the same filings and fuses the rankings with reciprocal rank
fusion.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

from copilot.llm import LLMClient, Message, system, user

Rewrite = Literal["multi", "hyde", "decompose"]
REWRITES: tuple[Rewrite, ...] = ("multi", "hyde", "decompose")
PROMPT_VERSION = "1"

_SYSTEM = {
    "multi": "You write search queries for finding passages in SEC filings: 10-Ks, 10-Qs, "
    "8-Ks and earnings releases.",
    "hyde": "You write short excerpts in the style of SEC filings.",
    "decompose": "You break analyst questions about company filings into the facts needed "
    "to answer them.",
}
_TASK = {
    "multi": "Write three different search queries that would find the passages answering "
    "this question. Use the words a filing would use: line items, statement and section "
    "names, the company's name and the fiscal period. Leave out any instructions about how "
    "to format, round or explain the answer. One query per line, no numbering.",
    "hyde": "Write the passage, three to five sentences, that the company's filing would "
    "contain to answer this question, in the filing's own wording: a few lines of a "
    "financial statement, or a paragraph of management's discussion. Use plausible figures "
    "if you don't know the real ones. Return only the passage.",
    "decompose": "List the separate facts that must be looked up in the company's filings "
    "to answer this question, as search queries, one per line, at most four. A ratio needs "
    "each of its parts; a change needs both periods. Leave out any instructions about how to "
    "format or round the answer. No numbering.",
}
LIMITS = {"multi": 3, "hyde": 1, "decompose": 4}
_MARKER = re.compile(r"^\s*(?:[-*\N{BULLET}]|\d+[.)]|query\s*\d*\s*:)\s*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Search:
    """One search to run: a query, or a passage to embed as a document (HyDE)."""

    text: str
    passage: bool = False
    source: str = "question"


def rewrite_messages(kind: Rewrite, question: str) -> list[Message]:
    return [system(_SYSTEM[kind]), user(f"Question: {question}\n\n{_TASK[kind]}")]


def parse_queries(text: str, limit: int) -> list[str]:
    """One query per non-empty line, without list markers or wrapping quotes."""
    queries = []
    for line in text.splitlines():
        query = _MARKER.sub("", line).strip().strip("\"'").strip()
        if query and query not in queries:
            queries.append(query)
    return queries[:limit]


def _searches(kind: Rewrite, text: str) -> list[Search]:
    if kind == "hyde":
        passage = " ".join(text.split())
        return [Search(passage, passage=True, source=kind)] if passage else []
    return [Search(query, source=kind) for query in parse_queries(text, LIMITS[kind])]


def rewrite(llm: LLMClient, kind: Rewrite, question: str) -> list[Search]:
    """The searches one rewrite produces for a question."""
    response = llm.complete(
        rewrite_messages(kind, question), role="fast", temperature=0.0, max_tokens=1024
    )
    return _searches(kind, response.text)


async def arewrite(llm: LLMClient, kind: Rewrite, question: str) -> list[Search]:
    response = await llm.acomplete(
        rewrite_messages(kind, question), role="fast", temperature=0.0, max_tokens=1024
    )
    return _searches(kind, response.text)


def expand(llm: LLMClient, question: str, kinds: tuple[Rewrite, ...]) -> list[Search]:
    """The original question, then each rewrite's searches."""
    searches = [Search(question)]
    for kind in kinds:
        searches += rewrite(llm, kind, question)
    return searches


async def aexpand(llm: LLMClient, question: str, kinds: tuple[Rewrite, ...]) -> list[Search]:
    """`expand` with the rewrites requested at the same time, as the doc agent runs them."""
    groups = await asyncio.gather(*(arewrite(llm, kind, question) for kind in kinds))
    return [Search(question), *(search for group in groups for search in group)]
