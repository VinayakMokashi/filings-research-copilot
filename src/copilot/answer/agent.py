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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from qdrant_client import QdrantClient

from copilot.answer.context import BUDGET_TOKENS, Source, pack
from copilot.answer.generate import Answer, generate
from copilot.config import Settings
from copilot.eval import financebench as fb
from copilot.ingest.embed import FastEmbedBM25, FastEmbedDense
from copilot.ingest.universe import read_companies
from copilot.llm import LLMClient, LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.retrieval.query import CompanyMatcher, Filing, filings_from, resolve, understand
from copilot.retrieval.rewrite import REWRITES, Rewrite, Search, expand
from copilot.retrieval.search import Hit, Searcher, reciprocal_rank_fusion

FETCH = 60
COLLECTION = "fb_page_bge-small"  # page chunks, bge-small vectors (ADR-0011)


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
            expand(self.llm, question, self.rewrites) if self.rewrites else [Search(question)]
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

    def answer(self, question: str) -> AgentAnswer:
        retrieval = self.retrieve(question)
        answer = generate(self.llm, question, self.context(retrieval))
        if answer.answerable:
            return AgentAnswer(answer, retrieval)
        documents = retrieval.filings
        if documents is not None:
            documents = self.company_filings(question) or documents
        widened = documents is not None and set(documents) != set(retrieval.filings or [])
        if not widened and not answer.missing.strip():
            return AgentAnswer(answer, retrieval)
        second = self.retrieve(question, documents, missing=answer.missing)
        sources = self.context(second, self.retry_budget)
        return AgentAnswer(generate(self.llm, question, sources), second, answer)


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    """The final answer, what retrieval found for it, and the first answer if it was retried."""

    answer: Answer
    retrieval: Retrieval
    first: Answer | None = None

    @property
    def retried(self) -> bool:
        return self.first is not None


def corpus_filings(settings: Settings) -> list[Filing]:
    """The evaluation corpus, which the index holds: the 84 filings behind FinanceBench's
    questions."""
    root = settings.data_dir / "raw" / "financebench"
    corpus = {question.doc_name for question in fb.load_questions(root)}
    documents = fb.load_documents(root)
    return filings_from(documents[name] for name in sorted(corpus))


def company_matcher() -> CompanyMatcher:
    """Finds the universe's companies by name, alias or ticker."""
    companies = read_companies()
    return CompanyMatcher(
        [company.name for company in companies],
        {company.name: company.ticker for company in companies},
    )


def build_searcher(settings: Settings, collection: str = COLLECTION) -> Searcher:
    """Search over `collection` with the models it was built with; loading them takes seconds."""
    cache_dir = settings.data_dir / "models"
    return Searcher(
        QdrantClient(url=settings.qdrant_url, timeout=120),
        collection,
        FastEmbedDense(cache_dir=cache_dir),
        FastEmbedBM25(cache_dir=cache_dir),
    )


def build_agent(
    settings: Settings, collection: str = COLLECTION, llm: LLMClient | None = None
) -> DocAgent:
    """The doc agent over the evaluation corpus.

    Model calls go through `llm`, or by default through the disk cache
    (data/cache/llm.jsonl), paced to stay under the free tier's tokens-a-minute limit.
    """
    if llm is None:
        models = role_models(settings)
        cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / "llm.jsonl", models)
        llm = PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
    filings = corpus_filings(settings)
    return DocAgent(build_searcher(settings, collection), company_matcher(), filings, llm)
