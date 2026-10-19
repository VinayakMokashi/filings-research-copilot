"""Context building: the numbered sources the answer model reads (step 3.3).

Retrieval returns ranked page chunks. The answer model gets the top ones as a numbered list
("[1] 3M, Form 10-K for fiscal 2018, PDF page 60"), in rank order, until a token budget is
spent. Two choices keep the context useful:

- **Whole pages.** A long page is split into more than one chunk. When one part of a page
  makes the list, its other parts follow it, if the budget allows, so a financial statement
  isn't cut in half.
- **No repeats, no overflow.** A chunk already in the list is skipped, and one that doesn't
  fit is skipped in favour of shorter ones further down, until the budget is used.

Sources are numbered from 1, the way the model cites them. Pages keep FinanceBench's 0-based
index internally; labels show the PDF page number a reader would see (index + 1).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from copilot.retrieval.query import Filing
from copilot.retrieval.search import Hit

BUDGET_TOKENS = 3000
FORM_NAMES = {
    "10k": "Form 10-K",
    "10q": "Form 10-Q",
    "8k": "Form 8-K",
    "earnings": "earnings release",
}

Siblings = Callable[[Hit], Sequence[Hit]]


@dataclass(frozen=True, slots=True)
class Source:
    """One numbered passage the answer model can cite."""

    number: int
    doc_name: str
    page: int  # 0-based, as FinanceBench counts
    label: str
    text: str
    tokens: int


def describe(doc_name: str, page: int, filings: Mapping[str, Filing]) -> str:
    """'3M, Form 10-K for fiscal 2018, PDF page 60', from the filing list."""
    filing = filings.get(doc_name)
    if filing is None:
        return f"{doc_name}, PDF page {page + 1}"
    form = FORM_NAMES.get(filing.form, filing.form)
    if filing.date is not None:
        year, month, day = filing.date
        period = f"dated {year}-{month:02d}-{day:02d}"
    elif filing.quarter is not None:
        period = f"for Q{filing.quarter} of fiscal {filing.year}"
    else:
        period = f"for fiscal {filing.year}"
    return f"{filing.company}, {form} {period}, PDF page {page + 1}"


def pack(
    hits: Sequence[Hit],
    filings: Mapping[str, Filing],
    budget: int = BUDGET_TOKENS,
    siblings: Siblings | None = None,
) -> list[Source]:
    """Numbered sources from ranked hits, within `budget` tokens; see the module docstring."""
    chosen: list[Hit] = []
    seen: set[str] = set()
    spent = 0

    def take(hit: Hit) -> None:
        nonlocal spent
        if hit.point_id in seen or spent + hit.tokens > budget:
            return
        seen.add(hit.point_id)
        chosen.append(hit)
        spent += hit.tokens

    for hit in hits:
        if spent >= budget:
            break
        before = len(chosen)
        take(hit)
        if siblings is not None and len(chosen) > before:
            for sibling in siblings(hit):
                if sibling.pages[:1] == hit.pages[:1]:
                    take(sibling)
    return [
        Source(
            number=number,
            doc_name=hit.doc_name,
            page=hit.pages[0],
            label=describe(hit.doc_name, hit.pages[0], filings),
            text=hit.text,
            tokens=hit.tokens,
        )
        for number, hit in enumerate(chosen, start=1)
    ]


def context_pages(sources: Sequence[Source]) -> set[tuple[str, int]]:
    """The (filing, page) pairs a context covers, for scoring context recall."""
    return {(source.doc_name, source.page) for source in sources}
