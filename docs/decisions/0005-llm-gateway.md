# ADR-0005: One LLM gateway built on LiteLLM's router

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** 0

## Context

Many components will call language models: query rewriting, routing, answer synthesis, SQL generation, validation and briefs. If each one calls a provider SDK directly, provider changes, retries, fallbacks and cost tracking get re-implemented in every place, and tests need network access.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| A provider SDK at each call site | Simple | Locked to one provider; no shared retries, fallbacks or cost tracking |
| OpenAI SDK against OpenAI-compatible endpoints (the text2sql-analyst approach) | Small and explicit | Fallbacks and cost tracking still hand-written |
| LangChain chat models | Large ecosystem | Heavy abstraction for a thin need |
| **LiteLLM router, in process** | One interface to many providers; retries and fallbacks; usage and cost per call; mock responses for tests | A large dependency with defaults that need care (see Consequences) |
| LiteLLM proxy server | Central keys and budgets across many apps | An extra service to run, unnecessary for one app |

## Decision

Every model call goes through `copilot.llm.LLMGateway`, which wraps a LiteLLM `Router`:

- Callers ask for a **role** (`strong` or `fast`), never a model id. Settings map roles to models.
- Each role is a router deployment; an optional **fallback chain** is shared by both roles.
- Failures surface as `LLMError`. `rate_limited` is set when the role's own model fails with a quota error (a fallback's error does not set it), and configured API keys are scrubbed from the message.
- Each response carries the text, the configured id of the deployment that served it, latency, token counts, cost, reasoning, and whether a fallback answered.
- `FakeLLM` implements the same `LLMClient` protocol for tests.

## Evidence

- 39 unit tests, all offline, cover role routing, the real router's fallback path, replies shaped like live Groq responses, reasoning in `<think>` tags and in provider fields, empty replies, unknown prices, error mapping, key redaction and repeated failures. Network access is refused during tests.
- The live smoke test (`uv run poe smoke`) runs once the Groq key is configured (Phase 0, step 0.8).

## Consequences

- Swapping providers or models is a settings change.
- LiteLLM defaults that the gateway overrides:
  - Its price map is downloaded at import unless `LITELLM_LOCAL_MODEL_COST_MAP=True`, and its own implicit `.env` loading runs unless `LITELLM_MODE` is set. `copilot/__init__.py` sets both, so configuration comes only from `copilot.config`.
  - The router puts a failing deployment into a cooldown, replacing the real error with "no deployments available". With one deployment per role that only hides the cause, so cooldowns are disabled.
  - Providers report their own model id (Groq drops the `groq/` prefix). The gateway therefore names the deployment the router used, and detects a fallback by the model group that answered.
  - The router registers unknown models with empty prices, which LiteLLM then bills at $0. The gateway reports `cost_usd=None` for models without token prices, never a made-up $0.
- If several services later need shared budgets, the same configuration can move to the LiteLLM proxy.

## References

- LiteLLM router: https://docs.litellm.ai/docs/routing
- Groq reasoning (the `reasoning` field of gpt-oss models): https://console.groq.com/docs/reasoning
