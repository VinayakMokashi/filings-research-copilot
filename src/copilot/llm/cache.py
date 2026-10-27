"""A disk cache for model calls, so experiments can be re-run without spending quota again.

Free model tiers allow a few hundred thousand tokens a day, and an evaluation run asks
the same questions many times while one part of the pipeline changes. `CachedLLM` wraps
any client: a call whose model, messages and parameters have been seen before returns the
stored response (marked `cached=True`) instead of calling the model.

Entries are appended to a JSON Lines file as they arrive, so an interrupted run keeps
everything it has paid for. A line that can't be read, such as one cut short when a run
was killed mid-write, is skipped and counted, and the call it held is made again.
`also_read` names other cache files to answer from without writing to them, so a run can
replay calls another run made while keeping its own new calls apart, in a file no other
process appends to.

The key includes the model the role resolves to, so changing a role's model never returns
another model's answer, and the settings the gateway always sends with that model (such as
reasoning turned off), so a reply made under other settings is never replayed. Sampling at
a non-zero temperature is still cached: a cached run replays the same sample, which is
what makes it repeatable.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from copilot.llm.base import LLMClient, LLMResponse, Message, ModelRole
from copilot.llm.gateway import model_params


def cache_key(model: str, messages: Sequence[Message], params: Mapping[str, Any]) -> str:
    payload = {
        "model": model,
        "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        "params": dict(sorted(params.items())),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class CachedLLM:
    """An LLM client that answers repeated calls from a JSON Lines file."""

    def __init__(
        self,
        client: LLMClient,
        path: Path,
        models: Mapping[ModelRole, str],
        also_read: Sequence[Path] = (),
    ) -> None:
        self._client = client
        self._path = path
        self._models = dict(models)
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self.skipped = 0
        for source in [*also_read, path]:
            self._load(source)

    def _load(self, path: Path) -> None:
        if not path.exists():
            return
        with path.open(encoding="utf-8") as lines:
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    self.skipped += 1
                    continue
                self._entries[record["key"]] = record["response"]

    def _key(
        self,
        messages: Sequence[Message],
        role: ModelRole,
        temperature: float | None,
        max_tokens: int | None,
        extra: Mapping[str, Any],
    ) -> str:
        model = self._models.get(role, role)
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **model_params(model),
            **extra,
        }
        return cache_key(model, messages, params)

    def _cached(self, key: str) -> LLMResponse | None:
        stored = self._entries.get(key)
        if stored is None:
            return None
        self.hits += 1
        return replace(LLMResponse(**stored), cached=True)

    def _store(self, key: str, response: LLMResponse) -> None:
        stored: dict[str, Any] = asdict(response)
        record = {"key": key, "response": stored}
        with self._lock:
            self._entries[key] = stored
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8", newline="\n") as out:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

    def complete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        key = self._key(messages, role, temperature, max_tokens, extra)
        cached = self._cached(key)
        if cached is not None:
            return cached
        self.misses += 1
        response = self._client.complete(
            messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
        )
        self._store(key, response)
        return response

    async def acomplete(
        self,
        messages: Sequence[Message],
        *,
        role: ModelRole = "fast",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> LLMResponse:
        key = self._key(messages, role, temperature, max_tokens, extra)
        cached = self._cached(key)
        if cached is not None:
            return cached
        self.misses += 1
        response = await self._client.acomplete(
            messages, role=role, temperature=temperature, max_tokens=max_tokens, **extra
        )
        self._store(key, response)
        return response
