"""The routers: the semantic vote, the LLM router's prompt and replies, and the cascade."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from copilot.agents import router
from copilot.agents.router import (
    CascadeRouter,
    LLMRouter,
    Route,
    SemanticRouter,
    decide,
    entity_mask,
    nearest,
    parse_route,
    route_centroids,
    vote,
)
from copilot.eval import routing
from copilot.eval.financebench import read_jsonl
from copilot.ingest.embed import HashingDense
from copilot.llm import FakeLLM, LLMError
from copilot.retrieval.query import CompanyMatcher

ROOT = Path(__file__).resolve().parents[1]

EXAMPLES: list[tuple[str, Route]] = [
    ("What risks does Netflix list in its annual report", "doc"),
    ("Which legal proceedings does Boeing disclose", "doc"),
    ("What was Nike revenue in 2022", "data"),
    ("What was Amazon net income in 2021", "data"),
    ("hello there", "smalltalk"),
    ("hi how are you", "smalltalk"),
]
FIGURE_QUESTION = "What was Nike revenue in 2023"


class RecordingEmbedder:
    """HashingDense that records the texts it embeds, as documents and as search queries."""

    key = "recording"
    dim = 64

    def __init__(self) -> None:
        self._inner = HashingDense()
        self.documents: list[str] = []
        self.queries: list[str] = []

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.documents.extend(texts)
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        self.queries.append(text)
        return self._inner.embed_query(text)


def test_vote_weights_the_k_nearest_examples_by_similarity() -> None:
    similarities = np.array([0.9, 0.8, 0.7, 0.1], dtype=np.float32)

    scores = vote(similarities, ["doc", "data", "doc", "data"], k=3)

    assert scores["doc"] == pytest.approx(1.6)
    assert scores["data"] == pytest.approx(0.8)
    assert scores["hybrid"] == 0.0


def test_vote_leaves_out_masked_examples() -> None:
    similarities = np.array([0.9, -np.inf, 0.5], dtype=np.float32)

    scores = vote(similarities, ["doc", "data", "data"], k=3)

    assert scores["doc"] == pytest.approx(0.9)
    assert scores["data"] == pytest.approx(0.5)


def test_vote_needs_a_label_per_similarity() -> None:
    with pytest.raises(ValueError, match="2 similarities for 1 examples"):
        vote(np.zeros(2, dtype=np.float32), ["doc"])


def test_decide_takes_the_largest_vote_with_its_share() -> None:
    route, share = decide({"doc": 1.0, "data": 3.0})

    assert route == "data"
    assert share == pytest.approx(0.75)
    assert decide({"data": 1.0, "doc": 1.0}) == ("doc", 0.5)  # ties: the earlier route
    assert decide({}) == ("doc", 0.0)


def test_semantic_router_routes_by_the_closest_examples() -> None:
    semantic = SemanticRouter(HashingDense(), EXAMPLES, k=2)

    decision = semantic.route(FIGURE_QUESTION)

    assert decision.route == "data"
    assert decision.router == "semantic"
    assert decision.confidence == 1.0
    assert set(decision.scores) == {"data"}
    assert decision.model is None
    assert decision.cost_usd == 0.0
    assert len(semantic) == 6


def test_semantic_router_leaves_out_excluded_examples() -> None:
    semantic = SemanticRouter(HashingDense(), EXAMPLES, k=1)

    assert semantic.route("hello there").route == "smalltalk"
    alone = semantic.route("hello there", exclude=[4, 5])
    assert alone.route == "doc"  # nothing similar is left, so nothing votes
    assert alone.confidence == 0.0


def test_semantic_router_embeds_questions_like_examples_unless_asked() -> None:
    embedder = RecordingEmbedder()
    SemanticRouter(embedder, EXAMPLES).route(FIGURE_QUESTION)
    assert embedder.queries == []

    SemanticRouter(embedder, EXAMPLES, instruction=True).route(FIGURE_QUESTION)
    assert embedder.queries == [FIGURE_QUESTION]


def test_semantic_router_needs_examples_and_a_positive_k() -> None:
    with pytest.raises(ValueError, match="examples"):
        SemanticRouter(HashingDense(), [])
    with pytest.raises(ValueError, match="k must"):
        SemanticRouter(HashingDense(), EXAMPLES, k=0)


def test_route_centroids_average_each_route_s_examples() -> None:
    vectors = np.array([[1, 0], [0, 1], [1, 0], [0.6, 0.8]], dtype=np.float32)
    labels: list[Route] = ["doc", "data", "doc", "data"]

    centroids = route_centroids(vectors, labels)

    assert set(centroids) == {"doc", "data"}
    np.testing.assert_allclose(centroids["doc"], [1.0, 0.0])
    assert float(np.linalg.norm(centroids["data"])) == pytest.approx(1.0)
    assert set(route_centroids(vectors, labels, exclude=[1, 3])) == {"doc"}


def test_nearest_takes_the_closest_centroid_with_its_margin() -> None:
    route, margin = nearest({"doc": 0.5, "data": 0.8, "brief": 0.6})

    assert route == "data"
    assert margin == pytest.approx(0.2)
    assert nearest({"data": 0.7, "doc": 0.7}) == ("doc", 0.0)  # ties: the earlier route
    assert nearest({"brief": 0.4}) == ("brief", 0.4)
    with pytest.raises(ValueError, match="No centroids"):
        nearest({})


def test_semantic_router_by_centroid_leaves_out_excluded_examples() -> None:
    semantic = SemanticRouter(HashingDense(), EXAMPLES, method="centroid")

    decision = semantic.route(FIGURE_QUESTION)

    assert decision.route == "data"
    assert decision.confidence is not None
    assert decision.confidence > 0
    assert semantic.route(FIGURE_QUESTION, exclude=[2, 3]).route != "data"


def test_semantic_router_masks_examples_and_questions_alike() -> None:
    embedder = RecordingEmbedder()

    SemanticRouter(embedder, EXAMPLES, mask=str.upper).route("hello there")

    assert embedder.documents == [text.upper() for text, _ in EXAMPLES] + ["HELLO THERE"]


def test_entity_mask_hides_companies_and_years() -> None:
    mask = entity_mask(CompanyMatcher(["Nike", "Coca-Cola"], {"Nike": "NKE", "Coca-Cola": "KO"}))

    assert (
        mask("What was Nike's revenue in fiscal year 2022?") == "What was Acme's revenue in 2020?"
    )
    assert mask("Compare Coca-Cola and NKE for FY2021 and 2019.") == (
        "Compare Acme and Acme for 2020 and 2020."
    )
    assert mask("Hi there!") == "Hi there!"


def test_llm_router_prompt_holds_definitions_rules_measures_and_examples() -> None:
    prompt = router.router_prompt()

    for route, definition in router.ROUTE_DEFINITIONS.items():
        assert f"- {route}: {definition}" in prompt
    assert all(rule in prompt for rule in router.LABELLING_RULES)
    assert "Capital expenditure; Dividends paid" in prompt
    assert '"How up to date is your information?" -> smalltalk' in prompt
    assert prompt.endswith('"<one of doc, data, hybrid, brief, smalltalk, decline>"}')


def test_llm_router_reads_the_route_and_reason() -> None:
    fake = FakeLLM(['{"reason": "Asks for a reported figure.", "route": "data"}'])

    decision = LLMRouter(fake).route("What was Oracle's revenue in 2022?")

    assert decision.route == "data"
    assert decision.reason == "Asks for a reported figure."
    assert decision.router == "llm"
    assert decision.model == "fake/strong"
    assert decision.prompt_tokens > 0
    assert decision.error is None
    call = fake.calls[0]
    assert call.role == "strong"
    assert call.extra["response_format"] == {"type": "json_object"}
    assert call.messages[0]["content"] == router.router_prompt()
    assert call.messages[1]["content"] == "Question: What was Oracle's revenue in 2022?"


@pytest.mark.parametrize("reply", ["not JSON", '{"route": "weather"}', '{"reason": "no route"}'])
def test_llm_router_falls_back_to_doc_on_a_bad_reply(reply: str) -> None:
    decision = LLMRouter(FakeLLM([reply])).route("Anything")

    assert decision.route == "doc"
    assert decision.error is not None


def test_parse_route_ignores_case_spaces_and_fences() -> None:
    assert parse_route('```json\n{"route": " Hybrid ", "reason": " why "}\n```') == (
        "hybrid",
        "why",
    )


def test_llm_router_raises_a_failed_call() -> None:
    with pytest.raises(LLMError):
        LLMRouter(FakeLLM([])).route("Anything")


def test_cascade_keeps_a_unanimous_semantic_route_without_a_call() -> None:
    fake = FakeLLM([])
    cascade = CascadeRouter(SemanticRouter(HashingDense(), EXAMPLES, k=2), LLMRouter(fake))

    decision = cascade.route(FIGURE_QUESTION)

    assert decision.route == "data"
    assert decision.router == "cascade"
    assert decision.model is None
    assert fake.calls == []


def test_cascade_asks_the_llm_below_the_threshold() -> None:
    fake = FakeLLM(['{"reason": "A figure and its reasons.", "route": "hybrid"}'])
    semantic = SemanticRouter(HashingDense(), EXAMPLES, k=2)

    decision = CascadeRouter(semantic, LLMRouter(fake), threshold=1.01).route(FIGURE_QUESTION)

    assert decision.route == "hybrid"
    assert decision.router == "cascade"
    assert decision.model == "fake/strong"
    assert decision.confidence == 1.0  # the semantic vote is kept for the record
    assert decision.scores


def test_cascade_falls_back_to_the_semantic_route() -> None:
    semantic = SemanticRouter(HashingDense(), EXAMPLES, k=2)

    failed = CascadeRouter(semantic, LLMRouter(FakeLLM([])), threshold=1.01).route(FIGURE_QUESTION)
    assert failed.route == "data"
    assert "LLM router failed" in (failed.error or "")

    unreadable = CascadeRouter(semantic, LLMRouter(FakeLLM(["nonsense"])), threshold=1.01)
    decision = unreadable.route(FIGURE_QUESTION)
    assert decision.route == "data"
    assert decision.model == "fake/strong"
    assert decision.error is not None

    strict = CascadeRouter(
        semantic, LLMRouter(FakeLLM([])), threshold=1.01, fallback_on_error=False
    )
    with pytest.raises(LLMError):
        strict.route(FIGURE_QUESTION)


def test_prompt_examples_are_not_routing_set_questions() -> None:
    questions = {record["query"].casefold() for record in read_jsonl(ROOT / routing.QUERIES_FILE)}

    for question, route in router.PROMPT_EXAMPLES:
        assert question.casefold() not in questions
        assert route in router.ROUTES
    assert {route for _, route in router.PROMPT_EXAMPLES} == set(router.ROUTES)


def test_the_prompt_states_the_database_s_grain_and_that_assessments_are_hybrid() -> None:
    from copilot.agents.router import GRAIN_RULES, PROMPT_VERSION, router_prompt

    prompt = router_prompt()

    assert PROMPT_VERSION == "r2"
    for rule in GRAIN_RULES:
        assert f"- {rule}" in prompt
    assert "annual figures for whole companies" in prompt
    assert "is not investment advice" in prompt
