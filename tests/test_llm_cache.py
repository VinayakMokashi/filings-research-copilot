"""The model-call cache: repeats come from disk, keys separate models and parameters."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from copilot.llm import FakeLLM, LLMResponse, ModelRole, user
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


def test_a_line_cut_short_is_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "llm.jsonl"
    CachedLLM(FakeLLM(["kept"]), path, MODELS).complete([user("q")])
    with path.open("a", encoding="utf-8") as out:
        out.write('{"key": "abc", "response": {"te')

    cache = CachedLLM(FakeLLM([]), path, MODELS)

    assert cache.skipped == 1
    assert cache.complete([user("q")]).text == "kept"


def test_keys_separate_messages_parameters_roles_and_models() -> None:
    base = cache_key("groq/qwen", [user("q")], {"temperature": 0.0})

    assert cache_key("groq/qwen", [user("q")], {"temperature": 0.0}) == base
    assert cache_key("groq/qwen", [user("q2")], {"temperature": 0.0}) != base
    assert cache_key("groq/qwen", [user("q")], {"temperature": 0.7}) != base
    assert cache_key("groq/gpt-oss", [user("q")], {"temperature": 0.0}) != base


def test_a_model_s_fixed_settings_are_part_of_its_key(tmp_path: Path) -> None:
    """Qwen on Cerebras is always called without reasoning, so a reply cached from a call
    without that setting isn't replayed; a model with no fixed settings keeps its old key."""
    path = tmp_path / "llm.jsonl"
    models: dict[ModelRole, str] = {"fast": "cerebras/qwen-3.8-27b", "strong": "groq/gpt-oss"}
    plain = {"temperature": None, "max_tokens": None}
    with path.open("w", encoding="utf-8") as out:
        for role, model in models.items():
            reply = LLMResponse(text=f"old {role}", role=role, model=model, latency_s=0.0)
            key = cache_key(model, [user("q")], plain)
            out.write(json.dumps({"key": key, "response": asdict(reply)}) + "\n")

    cache = CachedLLM(FakeLLM(["new fast"]), path, models)

    assert cache.complete([user("q")], role="strong").text == "old strong"
    assert cache.complete([user("q")], role="fast").text == "new fast"


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


def test_a_cache_answers_from_another_file_without_writing_to_it(tmp_path: Path) -> None:
    shared = tmp_path / "llm.jsonl"
    CachedLLM(FakeLLM(["from the shared file"]), shared, MODELS).complete([user("old")])
    before = shared.read_bytes()
    own = tmp_path / "hyde.jsonl"
    fake = FakeLLM(["a new call"])
    cached = CachedLLM(fake, own, MODELS, also_read=[shared])

    old = cached.complete([user("old")])
    new = cached.complete([user("new")])

    assert (old.text, old.cached) == ("from the shared file", True)
    assert (new.text, new.cached) == ("a new call", False)
    assert len(fake.calls) == 1
    assert shared.read_bytes() == before  # only the run's own file grows
    assert len(own.read_text(encoding="utf-8").splitlines()) == 1
