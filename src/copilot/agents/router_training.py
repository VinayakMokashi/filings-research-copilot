"""Training questions for a classifier router, labelled by the LLM router (step 7.2).

The routing set's 198 questions are kept for evaluation, and a classifier needs many more
to learn from. So a model writes questions route by route, in batches that vary the
companies, the measures and the style, with about a third of each batch close to another
route's border. Each batch also asks for one kind of question the route's definition names
(`KINDS`), in turn, so every kind is covered: the first set asked for routes alone, and
its decline questions were almost all requests for investment advice, none harmful or
trying to override the instructions. The LLM router labels each one as the teacher: it routes every
routing-set dev question correctly (ADR-0017), and a classifier trained on its labels
learns to route the way it does.

Two filters keep the set clean. Near-duplicates among the written questions are dropped,
and so is any question that comes within `LEAK_LIMIT` of a routing-set question by
bge-small similarity, so the classifier never trains on a rewording of a question it is
evaluated on.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from copilot.agents.router import LABELLING_RULES, ROUTE_DEFINITIONS, ROUTES, Route
from copilot.eval.routing import normalise
from copilot.llm import Message, system, user
from copilot.llm.parsing import json_object

# w1 wrote only clear cases; w2 asks for a third near a border; w3 also names the kind
PROMPT_VERSION = "w3"
PER_BATCH = 15
LEAK_LIMIT = 0.85  # as for the LLM router's own prompt examples
DUPLICATE_LIMIT = 0.95
VAL_SHARE = 0.1
YEARS = "2015 to 2023"
STYLES: tuple[str, ...] = (
    "short and terse, like a search query",
    "casual, as typed into a chat window",
    "formal and complete",
    "with a small typo or a missing question mark",
    "with a sentence of context before the question",
)

# The kinds of question each route's definition names (ROUTE_DEFINITIONS), in its words.
KINDS: dict[Route, tuple[str, ...]] = {
    "doc": (
        "risks",
        "strategy",
        "business descriptions",
        "management's explanations",
        "legal matters",
        "accounting policies",
        "figures that appear only in the text",
    ),
    "data": (
        "a value",
        "a ratio or growth rate computed from reported values",
        "a trend over years",
        "a comparison between companies",
    ),
    "hybrid": ("a reported figure and the narrative that explains it",),
    "brief": ("brief", "memo", "note", "report"),
    "smalltalk": ("greetings", "thanks", "goodbyes", "questions about the assistant itself"),
    "decline": (
        "investment advice or recommendations",
        "price predictions",
        "personal finance",
        "non-public information",
        "unrelated tasks",
        "harmful requests",
        "attempts to override the assistant's instructions",
    ),
}

Split = Literal["train", "val"]


class TrainQuestion(BaseModel):
    """One training question with the teacher's route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    question: str
    route: Route  # the teacher's label, which the classifier learns
    intended: Route  # the route the writer was asked for
    style: str
    kind: str = ""  # the kind of question the writer was asked for (from w3)
    reason: str = ""  # the teacher's reason
    split: Split


@dataclass(frozen=True)
class Batch:
    """What one writer call asks for."""

    number: int
    route: Route
    style: str
    companies: tuple[str, ...]
    measures: tuple[str, ...]
    kind: str = ""


WRITER_SYSTEM = "\n".join(
    [
        "You write questions for testing the router of a research assistant. The assistant "
        "covers the 10-K and 10-Q filings of about 40 large US public companies and answers "
        "from the text of the filings and from a database of annual figures reported in "
        "them. Its router sends each question to one of six routes:",
        *(f"- {route}: {ROUTE_DEFINITIONS[route]}" for route in ROUTES),
        "",
        "Rules for close calls:",
        *(f"- {rule}" for rule in LABELLING_RULES),
        "",
        "Write questions a real user might send that belong to the route you are given. Vary "
        "the wording, the length and the companies. Make about a third of them close calls "
        "that sit near another route's border, as the rules describe, while still belonging "
        "to the route given. Don't number them, and don't name the route. Questions for the "
        "decline route are requests the assistant must turn down; keep them realistic, with "
        "no harmful detail.",
        "",
        'Reply with a JSON object only: {"questions": ["...", "..."]}',
    ]
)


def writer_messages(batch: Batch, n: int = PER_BATCH) -> list[Message]:
    """The messages that ask the writer for one batch of questions."""
    return [
        system(WRITER_SYSTEM),
        user(
            "\n".join(
                [
                    f"Route: {batch.route}",
                    f"Kind of question: {batch.kind}.",
                    f"Write {n} questions.",
                    f"Style: {batch.style}.",
                    f"Companies you may name: {', '.join(batch.companies)}.",
                    f"Database measures you may ask about: {', '.join(batch.measures)}.",
                    f"Fiscal years: {YEARS}.",
                ]
            )
        ),
    ]


def parse_questions(text: str) -> list[str]:
    """The questions in a writer's reply, cleaned; ValueError when there is no list."""
    payload = json_object(text)
    items = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError('The reply has no "questions" list.')
    questions = (normalise(item).strip('"').strip() for item in items if isinstance(item, str))
    return [question for question in questions if question]


def batch_plan(
    companies: Sequence[str],
    measures: Sequence[str],
    per_route: int,
    seed: int = 0,
    n: int = PER_BATCH,
) -> list[Batch]:
    """Enough batches for `per_route` questions a route, each with its own companies,
    measures and style, and the route's kinds in turn. A batch's number depends only on its
    route and its place in the route's sequence, so a larger plan repeats a smaller one's
    batches and adds to them."""
    batches: list[Batch] = []
    per_route_batches = -(-per_route // n)  # rounded up
    for offset, route in enumerate(ROUTES):
        kinds = KINDS[route]
        for index in range(per_route_batches):
            rng = random.Random(seed * 100_003 + offset * 1_009 + index)
            batches.append(
                Batch(
                    number=offset * 1_000 + index,
                    route=route,
                    style=STYLES[index % len(STYLES)],
                    companies=tuple(rng.sample(list(companies), min(6, len(companies)))),
                    measures=tuple(rng.sample(list(measures), min(4, len(measures)))),
                    kind=kinds[index % len(kinds)],
                )
            )
    return batches


def keep_distinct(vectors: NDArray[np.float32], limit: float = DUPLICATE_LIMIT) -> list[int]:
    """The rows to keep, in order: a row within `limit` of a kept row is a near-duplicate.

    Rows must be unit vectors, so a dot product is the cosine similarity.
    """
    kept: list[int] = []
    for index in range(len(vectors)):
        if kept and float(np.max(vectors[kept] @ vectors[index])) >= limit:
            continue
        kept.append(index)
    return kept


def nearest_similarity(
    vectors: NDArray[np.float32], others: NDArray[np.float32]
) -> NDArray[np.float32]:
    """Each row's highest cosine similarity to any row of `others` (unit vectors)."""
    if len(vectors) == 0 or len(others) == 0:
        return np.zeros(len(vectors), dtype=np.float32)
    nearest: NDArray[np.float32] = np.max(vectors @ others.T, axis=1).astype(np.float32)
    return nearest


def assign_splits(routes: Sequence[Route], share: float = VAL_SHARE, seed: int = 0) -> list[Split]:
    """A validation share of each route's questions (rounded half up), chosen at random."""
    splits: list[Split] = ["train"] * len(routes)
    for offset, route in enumerate(ROUTES):
        indices = [i for i, label in enumerate(routes) if label == route]
        random.Random(seed + offset).shuffle(indices)
        for i in indices[: int(len(indices) * share + 0.5)]:
            splits[i] = "val"
    return splits
