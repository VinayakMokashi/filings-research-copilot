"""List the chat models your Groq key can use, and check the configured roles against them.

Usage: uv run poe models
"""

from __future__ import annotations

import sys

import httpx

from copilot.config import get_settings

GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"


def main() -> int:
    settings = get_settings()
    if settings.groq_api_key is None:
        print("GROQ_API_KEY is not set. Add it to .env and try again.", file=sys.stderr)
        return 1

    response = httpx.get(
        GROQ_MODELS_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}"},
        timeout=30,
    )
    if response.status_code != httpx.codes.OK:
        print(f"Groq returned HTTP {response.status_code}: {response.text[:200]}", file=sys.stderr)
        return 1

    available = sorted(model["id"] for model in response.json().get("data", []))
    print(f"{len(available)} models available to this key:")
    for model_id in available:
        print(f"  {model_id}")

    print()
    missing = False
    for role, model in (("strong", settings.llm_strong_model), ("fast", settings.llm_fast_model)):
        if not model.startswith("groq/"):
            print(f"{role:>6} role -> {model}: not a Groq model, not checked")
            continue
        found = model.removeprefix("groq/") in available
        missing = missing or not found
        print(f"{role:>6} role -> {model}: {'available' if found else 'NOT AVAILABLE'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
