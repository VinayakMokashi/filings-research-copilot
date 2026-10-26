"""Typed application settings, read from environment variables and a local `.env` file.

Project settings use the `FRC_` prefix (for example `FRC_LLM_FAST_MODEL`). Third-party
credentials keep their conventional names (`GROQ_API_KEY`, `SEC_USER_AGENT`, ...).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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

    # Local services
    qdrant_url: str = "http://127.0.0.1:6333"
    database_url: str = "postgresql://copilot:copilot@127.0.0.1:5433/copilot"

    # The API's conversations, notes and feedback: in memory, or in Postgres to outlive it
    api_state: Literal["memory", "postgres"] = "memory"
    # Questions a day before a 429: per visitor, and from everyone together (step 6.2)
    api_daily_questions: int = Field(default=20, ge=1)
    api_daily_total: int = Field(default=200, ge=1)
    # Days a stored answer to a repeated question is served again; 0 turns the cache off
    api_cache_days: int = Field(default=7, ge=0)
    # Where the web UI and the MCP server find the API
    api_url: str = "http://127.0.0.1:8000"

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
