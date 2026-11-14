"""Team-draft interleaving of two rankings (step 9.4; Radlinski, Kurup and Joachims, 2008).

A reader sees one list made from two rankings, the two teams. In each round the team with
fewer picks so far picks next, a coin breaking a tie, and adds its best result not yet in
the list; each result remembers the team that placed it. A click on a result credits its
team, and the team with more clicks on a search wins it.

Both rankings are judged by the same reader, on the same query, at the same moment, so a
handful of searches compares them more directly than two groups of readers shown one
ranking each could (Chapelle et al., 2012). Across searches, the wins are compared with a
sign test: if the rankings were equally good, each would win half the decided searches.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from copilot.retrieval.search import Hit

TEAMS = ("a", "b")


@dataclass(frozen=True, slots=True)
class Placed:
    """A result in the interleaved list, and the team that placed it."""

    hit: Hit
    team: str


def team_draft(a: Sequence[Hit], b: Sequence[Hit], k: int, rng: random.Random) -> list[Placed]:
    """At most `k` results from rankings `a` and `b`, interleaved; see the module docstring.
    A result both rankings hold appears once, for the team that placed it first."""
    rankings = {"a": list(a), "b": list(b)}
    at = {"a": 0, "b": 0}
    picks = {"a": 0, "b": 0}
    shown: list[Placed] = []
    seen: set[str] = set()

    def best_unseen(team: str) -> Hit | None:
        ranking = rankings[team]
        while at[team] < len(ranking) and ranking[at[team]].point_id in seen:
            at[team] += 1
        return ranking[at[team]] if at[team] < len(ranking) else None

    while len(shown) < k:
        candidates = {team: best_unseen(team) for team in TEAMS}
        open_teams = [team for team in TEAMS if candidates[team] is not None]
        if not open_teams:
            break
        if len(open_teams) == 1:
            team = open_teams[0]
        elif picks["a"] != picks["b"]:
            team = "a" if picks["a"] < picks["b"] else "b"
        else:
            team = "a" if rng.random() < 0.5 else "b"
        hit = candidates[team]
        assert hit is not None  # an open team has a candidate
        shown.append(Placed(hit, team))
        seen.add(hit.point_id)
        picks[team] += 1
    return shown


def winner(teams: Sequence[str], clicked: Iterable[int]) -> str | None:
    """Which team a search's clicks favour: `a`, `b`, `tie`, or None when nothing was clicked.
    A result clicked twice counts once."""
    counts = Counter(teams[position] for position in set(clicked) if 0 <= position < len(teams))
    if not counts:
        return None
    if counts["a"] == counts["b"]:
        return "tie"
    return "a" if counts["a"] > counts["b"] else "b"


def sign_test(wins_a: int, wins_b: int) -> float:
    """The two-sided exact p-value for `wins_a` against `wins_b`, if each were as likely to
    win a decided search; ties are left out before this."""
    decided = wins_a + wins_b
    if decided == 0:
        return 1.0
    tail = sum(math.comb(decided, i) for i in range(min(wins_a, wins_b) + 1))
    return min(1.0, 2 * tail / (1 << decided))
