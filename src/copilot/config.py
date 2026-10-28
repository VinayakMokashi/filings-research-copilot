"""Typed application settings, read from environment variables and a local `.env` file.

Project settings use the `FRC_` prefix (for example `FRC_LLM_FAST_MODEL`). Third-party
credentials keep their conventional names (`GROQ_API_KEY`, `SEC_USER_AGENT`, ...).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRC_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        validate_by_name=True,
    )

    # Application
    env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"

    # LLM provider credentials
    groq_api_key: SecretStr | None = Field(default=None, validation_alias="GROQ_API_KEY")
    cerebras_api_key: SecretStr | None = Field(default=None, validation_alias="CEREBRAS_API_KEY")
    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY"
    )

    # Langfuse traces of the API's runs (step 6.5): off unless both keys are set
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr | None = Field(
        default=None, validation_alias="LANGFUSE_SECRET_KEY"
    )
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )

    # The router's fallback when the LLM router's call fails (ADR-0017, ADR-0025): the
    # semantic router, or the fine-tuned classifier exported to router_model_dir
    router_fallback: Literal["semantic", "classifier"] = "semantic"
    router_model_dir: Path = Path("data/models/router-v2")

    # Hugging Face, for publishing the models trained in Phase 7
    hf_token: SecretStr | None = Field(default=None, validation_alias="HF_TOKEN")

    # The Qdrant collection the doc agent searches (ADR-0011); its index card names the
    # model its vectors came from, which then embeds the queries too (ADR-0027)
    collection: str = "fb_page_bge-small"

    # How the doc agent chooses its answer model (step 7.5): always the strong role, or an
    # epsilon-greedy bandit over copilot.answer.bandit.ARMS (its rewards come in Phase 9)
    answer_policy: Literal["fixed", "epsilon-greedy"] = "fixed"

    # Model roles, as LiteLLM model ids ("<provider>/<model>")
    llm_strong_model: str = "groq/openai/gpt-oss-120b"
    llm_fast_model: str = "groq/qwen/qwen3.8-27b"
    llm_small_model: str = "groq/openai/gpt-oss-20b"
    llm_fallback_models: str = Field(
        default="",
        description="Comma-separated LiteLLM model ids tried in order when a role's model fails.",
    )
    llm_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_tokens_per_minute: int | None = Field(
        default=8000,
        gt=0,
        description="Tokens a minute each model allows; batch jobs pause to stay under it.",
    )

    # Local data: downloads under data/raw, built databases under data/processed
    data_dir: Path = Path("data")

    # Local services, or their cloud counterparts in the deployment (ADR-0031)
    qdrant_url: str = "http://127.0.0.1:6333"
    # Qdrant Cloud's database key; a local Qdrant needs none
    qdrant_api_key: SecretStr | None = None
    database_url: str = "postgresql://copilot:copilot@127.0.0.1:5433/copilot"
    # Where the data agent's queries run (step 8.4): unset, on data/processed/facts.db; a
    # PostgreSQL URL (the read-only role on the facts database) runs them on the server,
    # with facts.db taking over while the server can't be reached
    facts_url: SecretStr | None = None

    # The API's state: in memory; in Postgres (conversations, notes, feedback, quotas, the
    # answer cache), to outlive the process; or in Firestore on Google Cloud (feedback,
    # quotas, the answer cache; conversations in memory), shared by every instance
    api_state: Literal["memory", "postgres", "firestore"] = "memory"
    # Questions a day before a 429: per visitor, and from everyone together (step 6.2)
    api_daily_questions: int = Field(default=20, ge=1)
    api_daily_total: int = Field(default=200, ge=1)
    # Days a stored answer to a repeated question is served again; 0 turns the cache off
    api_cache_days: int = Field(default=7, ge=0)
    # Where the web UI and the MCP server find the API
    api_url: str = "http://127.0.0.1:8000"
    # Send a Google ID token for the API's address with each call (Cloud Run, where only
    # the UI's and the MCP server's accounts may call the API)
    api_id_token: bool = False
    # Every run's events appended to data/traces/api.jsonl; off in the deployment, where
    # the file system is the instance's memory and traces go to Langfuse
    api_trace_file: bool = True
    # Model calls cached on disk under data/cache (replayed by evaluations); off in the
    # deployment, for the same reason
    llm_disk_cache: bool = True
    # Host names MCP clients may use for the HTTP transport, besides this machine's
    # (comma-separated; the Cloud Run service's own address in the deployment)
    mcp_allowed_hosts: str = ""

    # SEC EDGAR asks every client to identify itself as "Name contact@example.com".
    sec_user_agent: str | None = Field(default=None, validation_alias="SEC_USER_AGENT")

    @property
    def fallback_models(self) -> list[str]:
        """The fallback chain as a list, in the order it is tried."""
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings for the running process, read once."""
    return Settings()
