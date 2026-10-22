"""The data agent over the XBRL facts database (Phase 4).

text2sql-analyst's pipeline, set up for this project:

- **Every table is offered.** The facts database has seven tables, few enough to show the
  table-selection step whole, so `AllTablesRetriever` takes the place of a vector index.
  The descriptions are the hand-written ones in data/reference/facts_descriptions.json.
- **Value linking** (`copilot.sql.linking`): the companies a question names, the metric
  names, the definitions of combined measures and what fiscal years mean, as hints.
- **Model calls go through the gateway** (`GatewayLLM`): SQL on the strong model, table
  selection and the written analysis on the fast one (or the analysis on the strong one,
  with `analysis_model="strong"`), cached on disk in a file of their own and paced for
  the free tier.
- **Read-only SQL**, by text2sql-analyst's guardrails: one SELECT, checked by sqlglot; a
  read-only connection; an SQLite authorizer that refuses anything else; caps on rows,
  value size and time. A query that fails goes back to the model with the error, at most
  twice.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from text2sql.analysis import Analyst
from text2sql.config import Settings as Text2SQLSettings
from text2sql.db import read_schema
from text2sql.generation import SQLGenerator
from text2sql.pipeline import Pipeline
from text2sql.retrieval import AllTablesRetriever, TableSelector

from copilot.config import Settings
from copilot.llm import LLMClient, LLMGateway, ModelRole
from copilot.llm.cache import CachedLLM
from copilot.llm.pacing import PacedLLM
from copilot.sql.adapter import GatewayLLM
from copilot.sql.linking import FactsLinker

DESCRIPTIONS_FILE = Path("data/reference/facts_descriptions.json")
CACHE_FILE = "sql.jsonl"


def facts_db_path(settings: Settings) -> Path:
    return settings.data_dir / "processed" / "facts.db"


def batch_client(settings: Settings) -> PacedLLM:
    """The gateway behind a disk cache of its own, paced for the free tier."""
    models: dict[ModelRole, str] = {
        "fast": settings.llm_fast_model,
        "strong": settings.llm_strong_model,
    }
    cache = CachedLLM(LLMGateway(settings), settings.data_dir / "cache" / CACHE_FILE, models)
    return PacedLLM(cache, tokens_per_minute=settings.llm_tokens_per_minute)


def build_pipeline(
    settings: Settings,
    client: LLMClient | None = None,
    *,
    db_path: Path | None = None,
    descriptions: Mapping[str, str] | None = None,
    linking: bool = True,
    analysis_model: ModelRole = "fast",
) -> Pipeline:
    """text2sql-analyst's pipeline over the facts database, with this project's models.

    `linking=False` leaves out value linking, as the first baseline ran. `analysis_model`
    is the model that writes the answer from the rows.
    """
    path = db_path or facts_db_path(settings)
    # The models come from the gateway, so text2sql-analyst's own provider is never used.
    options = Text2SQLSettings(db_path=path, llm_provider="fake")
    schemas = read_schema(path, options.sample_rows)
    if descriptions is None:
        descriptions = json.loads(DESCRIPTIONS_FILE.read_text(encoding="utf-8"))
    llm = client or batch_client(settings)
    helper = GatewayLLM(llm, "helper", settings.llm_fast_model)
    sql_llm = GatewayLLM(llm, "sql", settings.llm_strong_model)
    return Pipeline(
        options,
        schemas,
        AllTablesRetriever(schemas, descriptions),
        TableSelector(helper),
        SQLGenerator(sql_llm, options.sql_dialect, options.sample_rows),
        Analyst(sql_llm if analysis_model == "strong" else helper, options.analysis_rows),
        linker=FactsLinker.read(path) if linking else None,
    )
