"""Live smoke test: one small call per model role through the LLM gateway.

Usage: uv run poe smoke   (needs GROQ_API_KEY in .env)
"""

from __future__ import annotations

import sys

from copilot.config import get_settings
from copilot.llm import LLMError, LLMGateway, ModelRole, user
from copilot.logs import configure_logging

ROLES: tuple[ModelRole, ...] = ("fast", "strong", "small")
PROMPT = "Reply with exactly one word: ready"


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if settings.groq_api_key is None:
        print("GROQ_API_KEY is not set. Add it to .env and try again.", file=sys.stderr)
        return 1

    gateway = LLMGateway(settings)
    failures = 0
    for role in ROLES:
        try:
            response = gateway.complete([user(PROMPT)], role=role, max_tokens=1024)
        except LLMError as exc:
            failures += 1
            reason = "rate limited" if exc.rate_limited else "failed"
            print(f"{role:>6}: {reason}: {exc}", file=sys.stderr)
            continue
        cost = f"${response.cost_usd:.6f}" if response.cost_usd is not None else "unknown cost"
        print(
            f"{role:>6}: {response.model} replied {response.text!r} in {response.latency_s:.2f}s "
            f"({response.prompt_tokens} in / {response.completion_tokens} out tokens, {cost})"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
