"""Gateway tests. LiteLLM's `mock_response` serves replies locally, so no network is used."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from litellm.exceptions import APIConnectionError, AuthenticationError, RateLimitError
from litellm.router import Router
from litellm.types.utils import ModelResponse
from pydantic import SecretStr

from copilot.config import Settings
from copilot.llm import LLMError, LLMGateway, user
from copilot.llm.gateway import api_key_for, build_router, provider_of

# --- Happy paths through a real LiteLLM router ---------------------------------------------


def test_complete_returns_text_usage_and_model(settings: Settings) -> None:
    response = LLMGateway(settings).complete([user("hi")], mock_response="Hello there")

    assert response.text == "Hello there"
    assert response.role == "fast"
    assert response.model == settings.llm_fast_model
    assert (response.prompt_tokens, response.completion_tokens) == (10, 20)
    assert response.latency_s >= 0
    assert response.fallback_used is False


def test_strong_role_uses_the_strong_model(settings: Settings) -> None:
    response = LLMGateway(settings).complete([user("hi")], role="strong", mock_response="ok")

    assert response.model == settings.llm_strong_model


def test_inline_reasoning_is_kept_out_of_the_answer(settings: Settings) -> None:
    response = LLMGateway(settings).complete(
        [user("sql please")], mock_response="<think>join two tables</think>SELECT 1"
    )

    assert response.text == "SELECT 1"
    assert response.reasoning == "join two tables"


def test_provider_reasoning_field_is_kept(settings: Settings) -> None:
    groq_reply = ModelResponse(
        model="openai/gpt-oss-120b",
        choices=[{"message": {"role": "assistant", "content": "ready", "reasoning": "plan"}}],
    )

    response = LLMGateway(settings).complete([user("hi")], role="strong", mock_response=groq_reply)

    assert (response.text, response.reasoning) == ("ready", "plan")


def test_async_completion(settings: Settings) -> None:
    gateway = LLMGateway(settings)

    response = asyncio.run(gateway.acomplete([user("hi")], role="strong", mock_response="async ok"))

    assert response.text == "async ok"
    assert response.model == settings.llm_strong_model


def test_fallback_served_reply_is_reported(settings: Settings) -> None:
    router = Router(
        model_list=[
            {
                "model_name": "fast",
                "litellm_params": {
                    "model": "groq/qwen/qwen3.8-27b",
                    "api_key": "k",
                    "mock_response": "litellm.InternalServerError",
                },
            },
            {
                "model_name": "fallback-1",
                "litellm_params": {
                    "model": "cerebras/gpt-oss-120b",
                    "api_key": "k",
                    "mock_response": "from the fallback",
                },
            },
        ],
        fallbacks=[{"fast": ["fallback-1"]}],
        num_retries=0,
        disable_cooldowns=True,
    )

    response = LLMGateway(settings, router=router).complete([user("hi")])

    assert response.text == "from the fallback"
    assert response.model == "cerebras/gpt-oss-120b"
    assert response.fallback_used is True


# --- Responses shaped like live provider replies ---------------------------------------------


class _StubRouter:
    """Returns one fixed response, shaped like a live router call."""

    def __init__(self, raw: ModelResponse) -> None:
        self.raw = raw

    def completion(self, **_: Any) -> Any:
        return self.raw

    async def acompletion(self, **_: Any) -> Any:
        return self.raw


def _routed(served: str, deployment: str, group: str) -> ModelResponse:
    raw = ModelResponse(
        model=served, choices=[{"index": 0, "message": {"role": "assistant", "content": "ok"}}]
    )
    raw._hidden_params = {
        "litellm_model_name": deployment,
        "additional_headers": {"x-litellm-model-group": group},
    }
    return raw


def _gateway_returning(settings: Settings, raw: ModelResponse) -> LLMGateway:
    return LLMGateway(settings, router=cast(Router, _StubRouter(raw)))


def test_live_groq_reply_names_the_configured_model(settings: Settings) -> None:
    # Groq answers with its own id ("openai/gpt-oss-120b"), without the "groq/" prefix.
    raw = _routed("openai/gpt-oss-120b", settings.llm_strong_model, "strong")

    response = _gateway_returning(settings, raw).complete([user("hi")], role="strong")

    assert response.model == settings.llm_strong_model
    assert response.fallback_used is False


def test_reply_from_a_fallback_group_is_flagged(settings: Settings) -> None:
    raw = _routed("gpt-oss-120b", "cerebras/gpt-oss-120b", "fallback-1")

    response = _gateway_returning(settings, raw).complete([user("hi")], role="strong")

    assert response.model == "cerebras/gpt-oss-120b"
    assert response.fallback_used is True


def test_a_reply_without_choices_becomes_an_llm_error(settings: Settings) -> None:
    with pytest.raises(LLMError, match="no choices"):
        _gateway_returning(settings, ModelResponse(choices=[])).complete([user("hi")])


# --- Cost -------------------------------------------------------------------------------------


def test_priced_models_report_a_cost(settings: Settings) -> None:
    response = LLMGateway(settings).complete([user("hi")], mock_response="ok")

    assert response.cost_usd is not None
    assert response.cost_usd > 0


def test_models_missing_from_the_price_map_have_unknown_cost() -> None:
    settings = Settings(
        _env_file=None,
        groq_api_key=SecretStr("test-groq-key"),
        llm_fast_model="groq/not-in-the-price-map",
    )

    response = LLMGateway(settings).complete([user("hi")], mock_response="ok")

    assert response.cost_usd is None


# --- Failures -----------------------------------------------------------------------------------


class _FailingRouter:
    """Stands in for a LiteLLM router whose retries and fallbacks are all exhausted."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def completion(self, **_: Any) -> Any:
        raise self.exc

    async def acompletion(self, **_: Any) -> Any:
        raise self.exc


def _gateway_failing_with(settings: Settings, exc: Exception) -> LLMGateway:
    return LLMGateway(settings, router=cast(Router, _FailingRouter(exc)))


def test_rate_limits_are_flagged(settings: Settings) -> None:
    exc = RateLimitError(message="slow down", llm_provider="groq", model="m")

    with pytest.raises(LLMError) as info:
        _gateway_failing_with(settings, exc).complete([user("hi")])

    assert info.value.rate_limited is True
    assert "RateLimitError" in str(info.value)


def test_other_failures_become_llm_errors(settings: Settings) -> None:
    exc = APIConnectionError(message="unreachable", llm_provider="groq", model="m")

    with pytest.raises(LLMError) as info:
        asyncio.run(_gateway_failing_with(settings, exc).acomplete([user("hi")]))

    assert info.value.rate_limited is False


def test_error_messages_never_contain_api_keys(settings: Settings) -> None:
    leaked = "gsk_" + "A1b2C3d4" * 3
    exc = APIConnectionError(
        message=f"upstream echoed test-groq-key and {leaked}", llm_provider="groq", model="m"
    )

    with pytest.raises(LLMError) as info:
        _gateway_failing_with(settings, exc).complete([user("hi")])

    assert "test-groq-key" not in str(info.value)
    assert leaked not in str(info.value)
    assert "[redacted]" in str(info.value)


def test_repeated_failures_keep_their_real_cause(settings: Settings) -> None:
    # Without disable_cooldowns, the second call would fail with "No deployments available".
    gateway = LLMGateway(settings)
    bad_key = AuthenticationError(message="invalid api key", llm_provider="groq", model="m")

    for _ in range(2):
        with pytest.raises(LLMError, match="AuthenticationError"):
            gateway.complete([user("hi")], mock_response=bad_key)


# --- Router construction -------------------------------------------------------------------


def test_provider_and_key_lookup() -> None:
    settings = Settings(
        _env_file=None, groq_api_key=SecretStr("g"), cerebras_api_key=SecretStr("c")
    )

    assert provider_of("groq/openai/gpt-oss-120b") == "groq"
    assert provider_of("gpt-4o") == ""
    assert api_key_for("groq/openai/gpt-oss-120b", settings) == "g"
    assert api_key_for("cerebras/gpt-oss-120b", settings) == "c"
    assert api_key_for("openrouter/qwen/q3", settings) is None


def test_router_has_one_deployment_per_role_and_the_fallback_chain() -> None:
    settings = Settings(
        _env_file=None, llm_fallback_models="cerebras/gpt-oss-120b,openrouter/qwen/q3"
    )

    router = build_router(settings)

    assert [d["model_name"] for d in router.model_list] == [
        "strong",
        "fast",
        "fallback-1",
        "fallback-2",
    ]
    assert router.fallbacks == [
        {"strong": ["fallback-1", "fallback-2"]},
        {"fast": ["fallback-1", "fallback-2"]},
    ]


def test_router_without_fallbacks_has_no_chain() -> None:
    router = build_router(Settings(_env_file=None))

    assert [d["model_name"] for d in router.model_list] == ["strong", "fast"]
    assert not router.fallbacks
