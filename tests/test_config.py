from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from copilot.config import Settings


def test_defaults_without_any_configuration() -> None:
    settings = Settings(_env_file=None)

    assert settings.env == "dev"
    assert settings.llm_strong_model == "groq/openai/gpt-oss-120b"
    assert settings.groq_api_key is None
    assert settings.fallback_models == []


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRC_LLM_FAST_MODEL", "groq/openai/gpt-oss-20b")
    monkeypatch.setenv("FRC_LLM_FALLBACK_MODELS", " cerebras/gpt-oss-120b, openrouter/qwen/q3 ,")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    settings = Settings(_env_file=None)

    assert settings.llm_fast_model == "groq/openai/gpt-oss-20b"
    assert settings.fallback_models == ["cerebras/gpt-oss-120b", "openrouter/qwen/q3"]
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "gsk_test"


def test_reads_a_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FRC_LOG_LEVEL=DEBUG\nGROQ_API_KEY=gsk_from_file\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "DEBUG"
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "gsk_from_file"


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")

    assert Settings(_env_file=None).groq_api_key is None


def test_secrets_never_appear_in_repr_or_dumps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_supersecret")

    settings = Settings(_env_file=None)

    assert "gsk_supersecret" not in repr(settings)
    assert "gsk_supersecret" not in str(settings.model_dump())


def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRC_LLM_MAX_RETRIES", "-1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
