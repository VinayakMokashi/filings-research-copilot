"""The copilot built from settings: its agents, router, clients and checkpointer (step 5.1).

`build_components` puts together what the graph's nodes call:

- the doc agent over the evaluation corpus, the data agent with its answer written on the
  `strong` model, and the hybrid of the two;
- the router of ADR-0017: the LLM router on the `strong` role decides, and the semantic
  router (company names and years masked, the nearest route centroid) decides only when
  the LLM call fails;
- a client for small talk, on the `small` role.

Every component's model calls go through a disk cache of its own under data/cache/, so a
repeated question costs nothing. `batch=True` paces the calls for the free tier's
tokens-a-minute limit, retries a rate-limited call after a pause, and lets a spent quota
stop the run, as evaluations need. An interactive question runs without pauses and
without retries: the router falls back to its semantic half, and a specialist replies
that the quota is spent.

`postgres_checkpointer` keeps conversations in the Compose Postgres (127.0.0.1:5433), so
they outlive the process.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from copilot.agents.graph import Components
from copilot.agents.router import CascadeRouter, LLMRouter, SemanticRouter, entity_mask
from copilot.answer.agent import build_agent
from copilot.answer.hybrid import HybridAgent
from copilot.config import Settings
from copilot.eval.routing import load_queries
from copilot.ingest.embed import FastEmbedDense
from copilot.ingest.universe import read_companies
from copilot.llm import LLMGateway
from copilot.llm.cache import CachedLLM
from copilot.llm.gateway import role_models
from copilot.llm.pacing import PacedLLM
from copilot.retrieval.query import CompanyMatcher
from copilot.sql.agent import build_pipeline
from copilot.sql.tool import DataAgent


def build_components(settings: Settings, *, batch: bool = False) -> Components:
    """The copilot's parts over the evaluation corpus; see the module docstring."""
    models = role_models(settings)

    def client(cache_file: str) -> PacedLLM:
        cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / cache_file, models)
        if batch:
            return PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)
        return PacedLLM(cache, pause_s=0.0, attempts=1)  # counts tokens; no pauses or retries

    doc_llm, sql_llm, router_llm, chat = (
        client(name) for name in ("llm.jsonl", "sql.jsonl", "router.jsonl", "chat.jsonl")
    )
    doc = build_agent(settings, llm=doc_llm)
    data = DataAgent(build_pipeline(settings, sql_llm, analysis_model="strong"))
    companies = read_companies()
    matcher = CompanyMatcher(
        [company.name for company in companies],
        {company.name: company.ticker for company in companies},
    )
    semantic = SemanticRouter(
        FastEmbedDense(cache_dir=settings.data_dir / "models"),
        [(query.query, query.route) for query in load_queries("dev")],
        method="centroid",
        mask=entity_mask(matcher),
    )
    router = CascadeRouter(
        semantic,
        LLMRouter(router_llm, role="strong"),
        threshold=math.inf,  # the LLM router always decides; see ADR-0017
        fallback_on_error=not batch,
    )
    return Components(
        router=router,
        doc=doc,
        data=data,
        hybrid=HybridAgent(doc, data),
        matcher=matcher,
        chat=chat,
        companies=[company.name for company in companies],
        meters=[doc_llm, sql_llm, router_llm, chat],
        strict=batch,
    )


@contextmanager
def postgres_checkpointer(settings: Settings) -> Iterator[PostgresSaver]:
    """A checkpointer on the configured Postgres, with its tables created if missing."""
    with PostgresSaver.from_conn_string(settings.database_url) as saver:
        saver.setup()
        yield saver
