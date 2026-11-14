"""The doc agent: from a question to a grounded, cited answer, or an honest refusal (Phase 3).

1. **Retrieve** (ADR-0012): resolve the filings the question is about, rewrite the question
   three ways, search each rewrite and the question itself with dense vectors inside those
   filings, and fuse the rankings.
2. **Build the context** (step 3.3): the best chunks, in rank order, as numbered sources
   within a 3,000-token budget. Adding the other parts of split pages lowered how often an
   evidence page made the context, so it is off by default.
3. **Answer** (step 3.4): the answer model writes a cited answer from the sources only, with
   arithmetic left to the calculator, or says what is missing.
4. **Correct once** (a light form of corrective RAG): when the model says the sources lack
   something, search again for what it said was missing, across all of the company's
   filings, and ask once more. That search counts as much as all the others together, so
   its best pages rank alongside the best of the first search, and the second context is
   half as large again (4,500 tokens), so the pages that held the rest of the answer can
   stay. The rewrites come from the cache, so the retry costs one answer call.

Which model setting writes the answer, the arm, is fixed unless a bandit chooses it (steps
7.5 and 9.3, `copilot.answer.bandit`). A second answer to the same question names the first
one's arm to avoid, and gets another, from the bandit or, without one, at random on the doc
agent's own client.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from qdrant_client import QdrantClient

from copilot.answer.bandit import ArmChooser, ArmPolicy, Choice, other_arm
from copilot.answer.context import BUDGET_TOKENS, Source, pack
from copilot.answer.generate import Answer, generate
from copilot.config import Settings
from copilot.eval import financebench as fb
from copilot.ingest.embed import FastEmbedBM25, FastEmbedDense, dense_for_card
from copilot.ingest.index import read_card
from copilot.ingest.universe import read_companies
from copilot.llm import LLMClient, LLMError, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.logs import get_logger
from copilot.retrieval.query import CompanyMatcher, Filing, filings_from, resolve, understand
from copilot.retrieval.rewrite import REWRITES, HydePrompt, Rewrite, Search, expand
from copilot.retrieval.search import Hit, Searcher, reciprocal_rank_fusion

FETCH = 60

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Retrieval:
    """What retrieval found for one question."""

    filings: list[str] | None  # the filings searched; None means all of them
    searches: list[Search]
    hits: list[Hit]


class DocAgent:
    """Holds what every question needs: the filing list, the searcher and the model."""

    def __init__(
        self,
        searcher: Searcher,
        matcher: CompanyMatcher,
        filings: Sequence[Filing],
        llm: LLMClient,
        *,
        rewrites: tuple[Rewrite, ...] = REWRITES,
        budget: int = BUDGET_TOKENS,
        retry_budget: int | None = None,
        siblings: bool = False,
        hyde: HydePrompt | None = None,
        arms: ArmPolicy | None = None,
    ) -> None:
        self.searcher = searcher
        self.matcher = matcher
        self.filings = list(filings)
        self.by_name = {filing.doc_name: filing for filing in filings}
        self.llm = llm
        self.rewrites = rewrites
        self.budget = budget
        self.retry_budget = retry_budget or budget * 3 // 2
        self.siblings = siblings
        self.hyde = hyde
        self.arms = arms
        self._rng = random.Random()

    def retrieve(
        self,
        question: str,
        documents: list[str] | Literal["auto"] | None = "auto",
        missing: str = "",
    ) -> Retrieval:
        """Search for `question` in `documents`: resolved from the question by default, or all.

        With `missing`, also search for that text, weighted as much as all other searches.
        """
        if documents == "auto":
            documents = resolve(understand(question, self.matcher), self.filings)
        searches = (
            expand(self.llm, question, self.rewrites, self.hyde)
            if self.rewrites
            else [Search(question)]
        )
        weights = [1.0] * len(searches)
        if missing.strip():
            searches = [*searches, Search(missing.strip(), source="missing")]
            weights.append(float(len(weights)))
        rankings = [
            self.searcher.search(search.text, "dense", FETCH, documents, passage=search.passage)
            for search in searches
        ]
        if len(rankings) == 1:
            hits = rankings[0]
        else:
            hits = reciprocal_rank_fusion(rankings, weights=weights)[:FETCH]
        return Retrieval(documents, searches, hits)

    def context(self, retrieval: Retrieval, budget: int | None = None) -> list[Source]:
        siblings = (lambda hit: self.searcher.neighbours(hit, 1)) if self.siblings else None
        return pack(retrieval.hits, self.by_name, budget or self.budget, siblings)

    def company_filings(self, question: str) -> list[str] | None:
        """All filings of the companies the question names, or None when it names none."""
        companies = set(understand(question, self.matcher).companies)
        names = sorted(f.doc_name for f in self.filings if f.company in companies)
        return names or None

    def answer(self, question: str, avoid: str | None = None) -> AgentAnswer:
        """The answer, from the arm the bandit chooses when one is set (steps 7.5 and 9.3);
        `avoid` asks for another arm than a first answer's."""
        choice = self.choose(avoid)
        retrieval = self.retrieve(question)
        answer, choice = self._write(question, self.context(retrieval), choice)
        if answer.answerable:
            return _answered(answer, retrieval, None, choice)
        documents = retrieval.filings
        if documents is not None:
            documents = self.company_filings(question) or documents
        widened = documents is not None and set(documents) != set(retrieval.filings or [])
        if not widened and not answer.missing.strip():
            return _answered(answer, retrieval, None, choice)
        second = self.retrieve(question, documents, missing=answer.missing)
        sources = self.context(second, self.retry_budget)
        final, choice = self._write(question, sources, choice)
        return _answered(final, second, answer, choice)

    def choose(self, avoid: str | None = None) -> Choice | None:
        """The answer's arm, or None for the fixed one. A second answer always gets another
        arm: the bandit's, or without one (or at its cap) one at random here."""
        choice = self.arms.choose(avoid) if self.arms is not None else None
        if choice is None and avoid is not None:
            choice = Choice(other_arm(avoid, self._rng), "retry")
        return choice

    def _write(
        self, question: str, sources: list[Source], choice: Choice | None
    ) -> tuple[Answer, Choice | None]:
        """One answer call with the choice's arm. A paid arm's failed call is written again
        on the fixed path, which then keeps the rest of the answer."""
        if choice is None:
            return generate(self.llm, question, sources), None
        arm = choice.arm
        try:
            written = generate(
                choice.llm or self.llm, question, sources, role=arm.role, **arm.settings
            )
        except LLMError as exc:
            if choice.llm is None:  # the doc agent's own client: its errors are the caller's
                raise
            log.warning("bandit.arm_failed", arm=arm.name, error=type(exc).__name__)
            return generate(self.llm, question, sources), None
        return written, choice


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    """The final answer, what retrieval found for it, and the first answer if it was retried."""

    answer: Answer
    retrieval: Retrieval
    first: Answer | None = None
    arm: str | None = None  # the arm that wrote it, when it wasn't the fixed path
    assignment: str | None = None  # why: "policy", "control" or "retry"

    @property
    def retried(self) -> bool:
        return self.first is not None


def _answered(
    answer: Answer, retrieval: Retrieval, first: Answer | None, choice: Choice | None
) -> AgentAnswer:
    if choice is None:
        return AgentAnswer(answer, retrieval, first)
    return AgentAnswer(answer, retrieval, first, choice.arm.name, choice.assignment)


# The corpus's metadata for an image that carries no FinanceBench files (`poe bundle-data`).
CORPUS_FILE = Path("processed") / "corpus.jsonl"


def corpus_documents(settings: Settings) -> list[fb.Document]:
    """The evaluation corpus, which the index holds: the 84 filings behind FinanceBench's
    questions, by name. Read from data/processed/corpus.jsonl when it exists, as in the
    deployed image, and otherwise from FinanceBench's own files."""
    manifest = settings.data_dir / CORPUS_FILE
    if manifest.is_file():
        lines = manifest.read_text(encoding="utf-8").splitlines()
        documents = [fb.Document.model_validate_json(line) for line in lines if line.strip()]
        return sorted(documents, key=lambda document: document.doc_name)
    root = settings.data_dir / "raw" / "financebench"
    corpus = {question.doc_name for question in fb.load_questions(root)}
    by_name = fb.load_documents(root)
    return [by_name[name] for name in sorted(corpus)]


def corpus_filings(settings: Settings) -> list[Filing]:
    """The corpus's filings, as the resolver needs them."""
    return filings_from(corpus_documents(settings))


def company_matcher() -> CompanyMatcher:
    """Finds the universe's companies by name, alias or ticker."""
    companies = read_companies()
    return CompanyMatcher(
        [company.name for company in companies],
        {company.name: company.ticker for company in companies},
    )


def build_searcher(settings: Settings, collection: str | None = None) -> Searcher:
    """Search over `collection` (the settings' by default) with the models it was built with.

    The collection's index card names its dense model; without a card, it is bge-small.
    Loading the models takes seconds.
    """
    name = collection or settings.collection
    cache_dir = settings.data_dir / "models"
    card = read_card(settings.data_dir, name)
    return Searcher(
        QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            timeout=120,
        ),
        name,
        dense_for_card(card, settings.data_dir) if card else FastEmbedDense(cache_dir=cache_dir),
        FastEmbedBM25(cache_dir=cache_dir),
    )


def build_agent(
    settings: Settings,
    collection: str | None = None,
    llm: LLMClient | None = None,
    arms: ArmPolicy | None = None,
) -> DocAgent:
    """The doc agent over the evaluation corpus.

    Model calls go through `llm`, or by default through the disk cache
    (data/cache/llm.jsonl), paced to stay under the free tier's tokens-a-minute limit. The
    arms are chosen by `arms` (the API's online bandit), or with
    `FRC_ANSWER_POLICY=epsilon-greedy` by a chooser kept in a file.
    """
    if llm is None:
        models = role_models(settings)
        cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "llm.jsonl", models)
        llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    filings = corpus_filings(settings)
    if arms is None and settings.answer_policy == "epsilon-greedy":
        arms = ArmChooser(settings.data_dir / "processed" / "bandit" / "answer-arms.json")
    searcher = build_searcher(settings, collection)
    return DocAgent(searcher, company_matcher(), filings, llm, arms=arms)
