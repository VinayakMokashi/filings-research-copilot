"""The model-call cache: repeats come from disk, keys separate models and parameters."""

from __future__ import annotations

import asyncio
from pathlib import Path

from copilot.llm import FakeLLM, ModelRole, user
from copilot.llm.cache import CachedLLM, cache_key

MODELS: dict[ModelRole, str] = {"fast": "groq/qwen", "strong": "groq/gpt-oss"}


def test_a_repeated_call_is_answered_from_the_file(tmp_path: Path) -> None:
    fake = FakeLLM(["first answer", "second answer"])
    cached = CachedLLM(fake, tmp_path / "llm.jsonl", MODELS)

    one = cached.complete([user("What was 3M's capex?")], temperature=0.0)
    two = cached.complete([user("What was 3M's capex?")], temperature=0.0)

    assert (one.text, one.cached) == ("first answer", False)
    assert (two.text, two.cached) == ("first answer", True)
    assert len(fake.calls) == 1
    assert (cached.hits, cached.misses) == (1, 1)


def test_the_cache_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "llm.jsonl"
    CachedLLM(FakeLLM(["kept"]), path, MODELS).complete([user("q")])

    again = CachedLLM(FakeLLM([]), path, MODELS).complete([user("q")])

    assert (again.text, again.cached) == ("kept", True)


def test_keys_separate_messages_parameters_roles_and_models() -> None:
    base = cache_key("groq/qwen", [user("q")], {"temperature": 0.0})

    assert cache_key("groq/qwen", [user("q")], {"temperature": 0.0}) == base
    assert cache_key("groq/qwen", [user("q2")], {"temperature": 0.0}) != base
    assert cache_key("groq/qwen", [user("q")], {"temperature": 0.7}) != base
    assert cache_key("groq/gpt-oss", [user("q")], {"temperature": 0.0}) != base


def test_roles_use_their_own_model_in_the_key(tmp_path: Path) -> None:
    fake = FakeLLM(["fast reply", "strong reply"])
    cached = CachedLLM(fake, tmp_path / "llm.jsonl", MODELS)

    fast = cached.complete([user("q")], role="fast")
    strong = cached.complete([user("q")], role="strong")

    assert (fast.text, strong.text) == ("fast reply", "strong reply")


def test_async_calls_share_the_cache(tmp_path: Path) -> None:
    fake = FakeLLM(["async answer"])
    cached = CachedLLM(fake, tmp_path / "llm.jsonl", MODELS)

    first = asyncio.run(cached.acomplete([user("q")]))
    second = cached.complete([user("q")])

    assert first.text == second.text == "async answer"
    assert second.cached
