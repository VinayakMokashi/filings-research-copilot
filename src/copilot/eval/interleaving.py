"""The search page's interleaving, counted (step 9.4, ADR-0038).

Each search record holds its teams in list order and the positions readers opened. A
search with clicks goes to the team with more of them, or is a tie; the wins are compared
with a sign test. With the traffic the deployment has, the counts are illustrative: they
show the method working, not which ranking is better.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from statistics import fmean
from typing import Any

from copilot.retrieval.interleaving import sign_test, winner

RANKERS = {"a": "dense", "b": "hybrid (dense and BM25)"}


def clicked(record: Mapping[str, Any]) -> list[int]:
    """The positions a search's readers opened: Firestore's `click_<position>` fields, or a
    memory log's `clicks` map."""
    found = [int(key.removeprefix("click_")) for key in record if key.startswith("click_")]
    clicks = record.get("clicks")
    if isinstance(clicks, Mapping):
        found += [int(position) for position in clicks]
    return sorted(set(found))


def tally(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Searches, clicks, wins by team and the sign test's p-value."""
    searches = list(records)
    outcomes = Counter(winner(record.get("teams") or [], clicked(record)) for record in searches)
    clicks = Counter(
        (record.get("teams") or [])[position]
        for record in searches
        for position in clicked(record)
        if position < len(record.get("teams") or [])
    )
    overlaps = [
        float(record["overlap"]) for record in searches if record.get("overlap") is not None
    ]
    return {
        "rankers": RANKERS,
        "searches": len(searches),
        "with_clicks": len(searches) - outcomes[None],
        "clicks": {team: clicks[team] for team in ("a", "b")},
        "wins": {"a": outcomes["a"], "b": outcomes["b"], "tie": outcomes["tie"]},
        "p": sign_test(outcomes["a"], outcomes["b"]),
        "mean_overlap": round(fmean(overlaps), 2) if overlaps else None,
    }
