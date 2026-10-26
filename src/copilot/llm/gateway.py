"""The single entry point for model calls.

Every call names a role (`strong`, `fast` or `small`) rather than a model. The gateway
maps roles to LiteLLM model ids from settings, retries transient failures, walks the
fallback chain, and reports tokens, cost and latency for each call.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import Any, cast

import litellm
from litellm.exceptions import RateLimitError
from litellm.router import Router
from litellm.types.utils import ModelResponse

from copilot.config import Settings
from copilot.llm.base import LLMError, LLMResponse, Message, ModelRole
from copilot.llm.reasoning import split_reasoning
from copilot.logs import get_logger

litellm.suppress_debug_info = True

log = get_logger(__name__)

# Which settings field holds the API key for each LiteLLM provider prefix.
_PROVIDER_KEY_FIELDS = {
    "groq": "groq_api_key",
    "cerebras": "cerebras_api_key",
    "openrouter": "openrouter_api_key",
}

# Key shapes for the providers this project uses. Error text is scrubbed of anything that
# looks like one, in case an upstream service echoes a key back in an error message.
_KEY_PATTERN = re.compile(r"\b(?:gsk_|csk-|sk-or-v1-|sk-lf-)[A-Za-z0-9_-]{16,}")

_TOKEN_PRICE_FIELDS = ("input_cost_per_token", "output_cost_per_token")

# Groq's error code once an organisation's monthly spend limit is reached (an HTTP 400).
SPEND_LIMIT = "blocked_api_access"


def provider_of(model: str) -> str:
    """`groq/openai/gpt-oss-120b` -> `groq`; an unprefixed id has no provider."""
    return model.split("/", 1)[0] if "/" in model else ""


def api_key_for(model: str, settings: Settings) -> str | None:
    """The configured key for a model's provider, or None to let LiteLLM decide."""
    field = _PROVIDER_KEY_FIELDS.get(provider_of(model))
    secret = getattr(settings, field) if field else None
    return secret.get_secret_value() if secret is not None else None


def role_models(settings: Settings) -> dict[ModelRole, str]:
    """The model each role resolves to; disk caches key their entries by it."""
    return {
        "strong": settings.llm_strong_model,
        "fast": settings.llm_fast_model,
        "small": settings.llm_small_model,
    }


def build_router(settings: Settings) -> Router:
    """A LiteLLM router with one deployment per role plus the shared fallback chain."""

    def deployment(name: str, model: str) -> dict[str, Any]:
        params: dict[str, Any] = {"model": model}
        key = api_key_for(model, settings)
        if key:
            params["api_key"] = key
        return {"model_name": name, "litellm_params": params}

    roles = role_models(settings)
    model_list = [deployment(role, model) for role, model in roles.items()]
    fallback_names: list[str] = []
    for index, model in enumerate(settings.fallback_models, start=1):
        name = f"fallback-{index}"
        model_list.append(deployment(name, model))
        fallback_names.append(name)

    fallbacks: list[dict[str, list[str]]] = (
        [{role: fallback_names} for role in roles] if fallback_names else []
    )
    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        num_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout_s,
        # Each role has a single deployment, so a cooldown would only swap the real error
        # (a bad key, say) for "no deployments available" during the cooldown window.
        disable_cooldowns=True,
    )


class LLMGateway:
    """Routes chat calls by role through LiteLLM and returns normalised responses."""

    def __init__(self, settings: Settings, router: Router | None = None) -> None:
        self._settings = settings
        self._router = router if router is not None else build_router(settings)
        self._secrets = [
            secret.get_secret_value()
            for secret in (
                settings.groq_api_key,
                settings.cerebras_api_key,
                settings.openrouter_api_key,
            )
            if secret is not None and secret.get_secret_value()
        ]

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        """One chat completion. Raises `LLMError` when retries and fallbacks are exhausted."""
        kwargs = self._call_kwargs(temperature, max_tokens, extra)
        started = time.perf_counter()
        try:
            raw = self._router.completion(model=role, messages=_payload(messages), **kwargs)
        except Exception as exc:
            raise self._error(exc, role) from exc
        return self._finish(raw, role, time.perf_counter() - started)

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        """Async version of `complete`."""
        kwargs = self._call_kwargs(temperature, max_tokens, extra)
        started = time.perf_counter()
        try:
            raw = await self._router.acompletion(
                model=role, messages=cast(Any, _payload(messages)), **kwargs
            )
        except Exception as exc:
            raise self._error(exc, role) from exc
        return self._finish(raw, role, time.perf_counter() - started)

    def _call_kwargs(
        self, temperature: float | None, max_tokens: int | None, extra: dict[str, Any]
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "temperature": self._settings.llm_temperature if temperature is None else temperature,
            **extra,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return kwargs

    def _error(self, exc: Exception, role: ModelRole) -> LLMError:
        # A reached spend limit means the same as a spent quota: stop, and try later.
        rate_limited = isinstance(exc, RateLimitError) or SPEND_LIMIT in str(exc)
        log.warning("llm.error", role=role, error=type(exc).__name__, rate_limited=rate_limited)
        message = self._redact(f"The {role} model call failed: {type(exc).__name__}: {exc}")
        return LLMError(message, rate_limited=rate_limited)

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[redacted]")
        return _KEY_PATTERN.sub("[redacted]", text)

    def _finish(self, raw: object, role: ModelRole, latency_s: float) -> LLMResponse:
        response = _to_response(raw, role, latency_s)
        log.info(
            "llm.call",
            role=role,
            model=response.model,
            latency_s=round(response.latency_s, 3),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=response.cost_usd,
            fallback_used=response.fallback_used,
        )
        return response


def _payload(messages: Sequence[Message]) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def _to_response(raw: object, role: ModelRole, latency_s: float) -> LLMResponse:
    if not isinstance(raw, ModelResponse):
        raise LLMError(f"Expected a complete response, got {type(raw).__name__}.")
    if not raw.choices:
        raise LLMError(f"The {role} model returned no choices.")

    message = getattr(raw.choices[0], "message", None)
    text, inline_reasoning = split_reasoning(getattr(message, "content", None) or "")
    # Providers return reasoning in a separate field (`reasoning_content` is LiteLLM's
    # standard name; Groq's gpt-oss models use `reasoning`) or inline as <think> tags.
    reasoning = (
        getattr(message, "reasoning_content", None)
        or getattr(message, "reasoning", None)
        or inline_reasoning
    )

    hidden: dict[str, Any] = getattr(raw, "_hidden_params", None) or {}
    headers: dict[str, Any] = hidden.get("additional_headers") or {}
    # Name the deployment the router used. raw.model is the provider's own id (Groq drops
    # the "groq/" prefix), and a fallback is a reply from a model group other than the role.
    model = str(hidden.get("litellm_model_name") or raw.model or "")
    group = headers.get("x-litellm-model-group") or role

    usage = getattr(raw, "usage", None)
    return LLMResponse(
        text=text,
        role=role,
        model=model,
        latency_s=latency_s,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        cost_usd=_cost(raw, hidden, model),
        reasoning=reasoning or None,
        fallback_used=group != role,
    )


def _cost(raw: ModelResponse, hidden: dict[str, Any], model: str) -> float | None:
    """Cost in USD, or None when LiteLLM has no prices for the model (never a made-up $0)."""
    if not _has_token_prices(model):
        return None
    cost = hidden.get("response_cost")
    if cost is None:
        try:
            cost = litellm.completion_cost(completion_response=raw)
        except Exception:
            return None
    return float(cost)


def _has_token_prices(model: str) -> bool:
    """Whether LiteLLM's price map holds token prices for `model`.

    The router registers every deployment in `litellm.model_cost`, with empty prices for
    models the bundled map does not know, and LiteLLM then prices their calls at $0.
    Reading the raw entry keeps an unknown price unknown.
    """
    try:
        key = litellm.get_model_info(model)["key"]
    except Exception:  # not in the price map at all
        return False
    entry = litellm.model_cost.get(key) or {}
    return any(entry.get(field) is not None for field in _TOKEN_PRICE_FIELDS)


def token_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """The list price of some tokens in US dollars, or None when LiteLLM has no prices."""
    if not _has_token_prices(model):
        return None
    prompt_cost, completion_cost = litellm.cost_per_token(
        model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return float(prompt_cost + completion_cost)
