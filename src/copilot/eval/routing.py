"""The routing eval set: labelled questions for the router that picks a specialist.

The set is built in three steps. Seed questions are written by hand, one per intent.
`paraphrase_messages` asks a model for rewrites of each seed, and each rewrite is reviewed
and accepted or rejected with a reason. `build` then splits the result into dev and a
held-out test side, keeping each seed and its paraphrases together so that no test
question is a rewording of a dev question.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# The routes and their definitions belong to the router; this module labels and scores.
from copilot.agents.router import ROUTE_DEFINITIONS as ROUTE_DEFINITIONS
from copilot.agents.router import ROUTES as ROUTES
from copilot.agents.router import Route as Route
from copilot.eval.financebench import ChecksumError, read_jsonl
from copilot.eval.splits import HeldOutError, records_sha256
from copilot.llm import Message, system, user

RoutingSplit = Literal["dev", "test"]
Origin = Literal["seed", "paraphrase"]

DIR = Path("eval/routing")
SEEDS_FILE = DIR / "seeds.jsonl"
CANDIDATES_FILE = DIR / "candidates.jsonl"
QUERIES_FILE = DIR / "queries.jsonl"
CHECKSUMS_FILE = DIR / "checksums.json"

PARAPHRASES_PER_SEED = 2

PARAPHRASE_SYSTEM = (
    "You write test data for the question router of a research assistant for company "
    "filings. Rewrite the query in three different ways. Keep its intent, company, period "
    "and every constraint, so each rewrite needs exactly the same kind of answer. Vary the "
    "wording and style: one short and terse, one casual, one longer and more formal. Do not "
    "add facts and do not answer the query. Reply with exactly three lines, one rewrite per "
    "line, with no numbering, bullets or quotes."
)


class Seed(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: str
    route: Route
    query: str


class Candidate(BaseModel):
    """A model-written paraphrase of a seed, with the reviewer's verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: str
    query: str
    model: str
    verdict: Literal["accept", "reject"] | None = None
    reason: str | None = None


class RoutingQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    query: str
    route: Route
    seed: str
    origin: Origin
    split: RoutingSplit


class Checksums(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    queries: int
    dev_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    test_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def load_seeds(path: Path = SEEDS_FILE) -> list[Seed]:
    return [Seed.model_validate(record) for record in read_jsonl(path)]


def load_candidates(path: Path = CANDIDATES_FILE) -> list[Candidate]:
    return [Candidate.model_validate(record) for record in read_jsonl(path)]


def paraphrase_messages(seed: Seed) -> list[Message]:
    route = f"Route: {seed.route} ({ROUTE_DEFINITIONS[seed.route]})"
    return [system(PARAPHRASE_SYSTEM), user(f"{route}\nQuery: {seed.query}")]


_LIST_MARKER = re.compile(r"^(?:\d+[.)]|[-*\u2022])\s*")
# Models write Unicode hyphens (U+2010, U+2011) where people type "-".
_HYPHENS = str.maketrans({"\u2010": "-", "\u2011": "-"})


def parse_paraphrases(text: str) -> list[str]:
    """One rewrite per non-empty line, without list markers or wrapping quotes."""
    lines = (
        _LIST_MARKER.sub("", line.strip()).strip().strip('"').strip() for line in text.splitlines()
    )
    return [line for line in lines if line]


def normalise(text: str) -> str:
    """Plain hyphens and single spaces, so typography from the model doesn't mark a query."""
    return " ".join(text.translate(_HYPHENS).split())


def assign_splits(seeds: Sequence[Seed], seed: int = 0) -> dict[str, RoutingSplit]:
    """Put 30% of each route's seeds (rounded half up) on the test side, chosen at random."""
    by_route: dict[Route, list[str]] = {}
    for item in seeds:
        by_route.setdefault(item.route, []).append(item.seed)
    sides: dict[str, RoutingSplit] = {}
    for offset, route in enumerate(ROUTES):
        ids = sorted(by_route.get(route, []))
        random.Random(seed + offset).shuffle(ids)
        test_count = (len(ids) * 3 + 5) // 10  # 30%, rounded half up
        for position, seed_id in enumerate(ids):
            sides[seed_id] = "test" if position < test_count else "dev"
    return sides


def build(seeds: Sequence[Seed], candidates: Sequence[Candidate]) -> list[RoutingQuery]:
    """Seeds plus their accepted paraphrases, numbered in seed order, with splits assigned.

    Every candidate must have a verdict, and every seed needs exactly
    `PARAPHRASES_PER_SEED` accepted paraphrases.
    """
    unreviewed = [c for c in candidates if c.verdict is None]
    if unreviewed:
        raise ValueError(f"{len(unreviewed)} candidates have no verdict yet.")
    accepted: dict[str, list[str]] = {}
    for candidate in candidates:
        if candidate.verdict == "accept":
            accepted.setdefault(candidate.seed, []).append(candidate.query)
    short = [s.seed for s in seeds if len(accepted.get(s.seed, [])) != PARAPHRASES_PER_SEED]
    if short:
        raise ValueError(
            f"Seeds without exactly {PARAPHRASES_PER_SEED} accepted paraphrases: "
            f"{', '.join(short)}."
        )
    sides = assign_splits(seeds)
    queries: list[RoutingQuery] = []
    for item in seeds:
        texts: list[tuple[str, Origin]] = [(normalise(item.query), "seed")]
        texts += [(normalise(text), "paraphrase") for text in accepted[item.seed]]
        for text, origin in texts:
            queries.append(
                RoutingQuery(
                    id=f"r{len(queries) + 1:03d}",
                    query=text,
                    route=item.route,
                    seed=item.seed,
                    origin=origin,
                    split=sides[item.seed],
                )
            )
    duplicates = [text for text, n in Counter(q.query.casefold() for q in queries).items() if n > 1]
    if duplicates:
        raise ValueError(f"Duplicate queries: {duplicates[:3]}")
    return queries


def checksums(queries: Sequence[RoutingQuery]) -> Checksums:
    def digest(side: RoutingSplit) -> str:
        return records_sha256(q.model_dump(mode="json") for q in queries if q.split == side)

    return Checksums(queries=len(queries), dev_sha256=digest("dev"), test_sha256=digest("test"))


def write_set(
    queries: Sequence[RoutingQuery],
    path: Path = QUERIES_FILE,
    checksums_path: Path = CHECKSUMS_FILE,
) -> None:
    lines = "".join(
        json.dumps(q.model_dump(mode="json"), ensure_ascii=False) + "\n" for q in queries
    )
    path.write_text(lines, encoding="utf-8", newline="\n")
    checksums_path.write_text(
        checksums(queries).model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def load_queries(
    split: RoutingSplit,
    *,
    allow_test: bool = False,
    path: Path = QUERIES_FILE,
    checksums_path: Path = CHECKSUMS_FILE,
) -> list[RoutingQuery]:
    """One side of the routing set, checked against the recorded checksum."""
    if split == "test" and not allow_test:
        raise HeldOutError(
            "The routing test split is held out for milestone evaluations. "
            "Pass allow_test=True only for one of those."
        )
    records = [record for record in read_jsonl(path) if record["split"] == split]
    expected = Checksums.model_validate_json(checksums_path.read_text(encoding="utf-8"))
    recorded = expected.dev_sha256 if split == "dev" else expected.test_sha256
    if records_sha256(records) != recorded:
        raise ChecksumError(f"The routing {split} queries differ from the recorded checksum.")
    return [RoutingQuery.model_validate(record) for record in records]


def score(queries: Sequence[RoutingQuery], predictions: Mapping[str, str]) -> list[dict[str, Any]]:
    """One row per query: the gold route, the predicted route and whether they match."""
    expected = {q.id for q in queries}
    missing, extra = expected - predictions.keys(), predictions.keys() - expected
    if missing or extra:
        raise ValueError(
            f"Predictions don't match the queries: {len(missing)} missing, {len(extra)} extra."
        )
    return [
        {
            "id": q.id,
            "route": q.route,
            "origin": q.origin,
            "predicted": predictions[q.id],
            "accuracy": 1.0 if predictions[q.id] == q.route else 0.0,
        }
        for q in queries
    ]


def confusion(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """How often each labelled route got each prediction, as rows from `score` give them."""
    matrix: dict[str, dict[str, int]] = {route: dict.fromkeys(ROUTES, 0) for route in ROUTES}
    for row in rows:
        counts = matrix.setdefault(str(row["route"]), dict.fromkeys(ROUTES, 0))
        counts[str(row["predicted"])] = counts.get(str(row["predicted"]), 0) + 1
    return matrix


def render_confusion(matrix: Mapping[str, Mapping[str, int]], title: str) -> str:
    """A confusion matrix as Markdown: a row per labelled route, a column per prediction."""
    columns = list(ROUTES) + sorted({p for counts in matrix.values() for p in counts} - {*ROUTES})
    lines = [
        f"# {title}",
        "",
        "Rows are the labelled route and columns the predicted one; the diagonal is correct, "
        "and empty cells are zero.",
        "",
        "| Labelled | " + " | ".join(columns) + " | Questions | Correct |",
        "|---" * (len(columns) + 3) + "|",
    ]
    for label, counts in matrix.items():
        cells = []
        for column in columns:
            count = counts.get(column, 0)
            cells.append(f"**{count}**" if column == label else (str(count) if count else ""))
        total = sum(counts.values())
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {total} | {counts.get(label, 0)} |")
    return "\n".join(lines) + "\n"


def read_predictions(path: Path) -> dict[str, str]:
    """Predictions as JSON Lines: `{"id": "r001", "route": "doc"}`."""
    predictions: dict[str, str] = {}
    for record in read_jsonl(path):
        if record["id"] in predictions:
            raise ValueError(f"{path} predicts {record['id']} more than once.")
        predictions[record["id"]] = str(record["route"])
    return predictions


# A keyword router: the floor any real router has to beat.
_SMALLTALK = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|bye)\b"
    r"|\b(who (built|made|are) you|what can you|how do you|do you cover)\b",
    re.IGNORECASE,
)
_DECLINE = re.compile(
    r"\b(should i|price (be|target)|invest in|retirement|insider|crypto|poem|taxes|hack"
    r"|ignore (your|all|previous)|system prompt|double)\b",
    re.IGNORECASE,
)
_BRIEF = re.compile(r"\b(brief|memo|note|report|profile|briefing|write|draft)\b", re.IGNORECASE)
_EXPLAIN = re.compile(
    r"\b(why|explain\w*|drivers?|drove|reasons?|factors?|priorities|plans?)\b", re.IGNORECASE
)
_FIGURE = re.compile(
    r"\b(revenue|income|eps|capex|capital expenditures?|cash flow|margin|ratio|assets|debt"
    r"|inventory|dividends?|r&d|spending|growth|how much)\b",
    re.IGNORECASE,
)


def keyword_route(query: str) -> Route:
    if _SMALLTALK.search(query):
        return "smalltalk"
    if _DECLINE.search(query):
        return "decline"
    if _BRIEF.search(query):
        return "brief"
    if _FIGURE.search(query):
        return "hybrid" if _EXPLAIN.search(query) else "data"
    return "doc"


def majority_route(queries: Sequence[RoutingQuery]) -> Route:
    """The most common gold route (ties go to the earlier route in `ROUTES`)."""
    counts = Counter(q.route for q in queries)
    return max(ROUTES, key=lambda route: (counts[route], -ROUTES.index(route)))
