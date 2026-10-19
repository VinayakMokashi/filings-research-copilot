"""Context building: numbered sources within a budget, labels, and split pages."""

from __future__ import annotations

from collections.abc import Sequence

from copilot.answer.context import context_pages, describe, pack
from copilot.retrieval.query import Filing
from copilot.retrieval.search import Hit

FILINGS = {
    "ACME_2022_10K": Filing("ACME_2022_10K", "Acme", "10k", 2022),
    "ACME_2023Q2_10Q": Filing("ACME_2023Q2_10Q", "Acme", "10q", 2023, 2),
    "ACME_2023_8K_dated-2023-08-30": Filing(
        "ACME_2023_8K_dated-2023-08-30", "Acme", "8k", 2023, None, (2023, 8, 30)
    ),
}


def _hit(name: str, page: int, tokens: int, doc: str = "ACME_2022_10K") -> Hit:
    return Hit(name, 1.0, doc, page, (page,), None, f"text of {name}", tokens)


def test_labels_name_the_company_form_period_and_reader_page() -> None:
    assert describe("ACME_2022_10K", 59, FILINGS) == "Acme, Form 10-K for fiscal 2022, PDF page 60"
    assert (
        describe("ACME_2023Q2_10Q", 0, FILINGS)
        == "Acme, Form 10-Q for Q2 of fiscal 2023, PDF page 1"
    )
    assert describe("ACME_2023_8K_dated-2023-08-30", 2, FILINGS) == (
        "Acme, Form 8-K dated 2023-08-30, PDF page 3"
    )


def test_pack_keeps_rank_order_skips_repeats_and_fills_the_budget() -> None:
    hits = [
        _hit("a", 1, 500),
        _hit("a", 1, 500),
        _hit("big", 2, 900),
        _hit("b", 3, 300),
        _hit("c", 4, 100),
    ]

    sources = pack(hits, FILINGS, budget=1000)

    assert [s.text for s in sources] == ["text of a", "text of b", "text of c"]
    assert [s.number for s in sources] == [1, 2, 3]
    assert context_pages(sources) == {
        ("ACME_2022_10K", 1),
        ("ACME_2022_10K", 3),
        ("ACME_2022_10K", 4),
    }


def test_split_pages_bring_their_other_part_along() -> None:
    first, rest, other = _hit("p5a", 5, 300), _hit("p5b", 5, 200), _hit("p6", 6, 300)

    def siblings(hit: Hit) -> Sequence[Hit]:
        return [rest, other] if hit is first else []

    sources = pack([first, _hit("p9", 9, 300)], FILINGS, budget=1000, siblings=siblings)

    assert [s.text for s in sources] == ["text of p5a", "text of p5b", "text of p9"]
