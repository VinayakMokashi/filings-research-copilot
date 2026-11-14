"""What the API served, kept so that a rating can store the answer it rates (step 9.2,
ADR-0035).

An exchange is one answer with what produced it:

- the question as asked and as the copilot read it, the route, and the arm that wrote it;
- the answer, whether it answered, and its citations;
- the numbered sources it was written from and the calculator's results, from the graph's
  state (`Copilot.details`);
- the validator's verdict, and the draft as it stood before its first check when it was
  revised;
- the models with their tokens, and the cost, from the run's usage events.

The API keeps the newest exchanges in memory, since it runs as one instance (ADR-0031).
Nothing is stored until a visitor rates one; an exchange the instance no longer holds is
simply not found.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from copilot.llm.gateway import token_cost

MAX_EXCHANGES = 256

# The source fields a record keeps: what the answer prompt and the judge need again.
SOURCE_FIELDS = ("number", "label", "doc_name", "page", "text")


def usage_of(events: Iterable[Mapping[str, Any]]) -> tuple[dict[str, list[int]], float | None]:
    """Prompt and completion tokens by model across a run's usage events, and their cost at
    list prices, or None when a model's price is unknown."""
    tokens: dict[str, list[int]] = {}
    for event in events:
        if event.get("event") != "usage":
            continue
        for model, (prompt, completion) in event.get("tokens_by_model", {}).items():
            used = tokens.setdefault(model, [0, 0])
            used[0] += int(prompt)
            used[1] += int(completion)
    prices = [
        token_cost(model, prompt, completion) for model, (prompt, completion) in tokens.items()
    ]
    known = [price for price in prices if price is not None]
    cost = round(sum(known), 7) if len(known) == len(prices) else None
    return tokens, cost


def exchange_record(
    *,
    request_id: str,
    thread_id: str,
    response: Mapping[str, Any],
    details: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    now: datetime,
    canary: bool = False,
    retry_of: str | None = None,
) -> dict[str, Any]:
    """One exchange as the API keeps it; `details` is empty for an answer from the cache."""
    result = details.get("result") or {}
    answer = result.get("answer") or {}
    draft = (details.get("draft") or {}).get("answer") or {}
    tokens, cost = usage_of(events)
    return {
        "request_id": request_id,
        "thread_id": thread_id,
        "turn": response.get("turn"),
        "created": now.isoformat(timespec="seconds"),
        "question": response.get("question", ""),
        "standalone": response.get("standalone") or response.get("question", ""),
        "route": response.get("route", ""),
        "kind": result.get("kind"),
        "text": response.get("text", ""),
        "answered": bool(response.get("answered")),
        "citations": list(response.get("citations") or []),
        "sources": [
            {key: source.get(key) for key in SOURCE_FIELDS} for source in answer.get("sources", [])
        ],
        "calculations": [
            {key: calculation.get(key) for key in ("id", "expression", "value")}
            for calculation in answer.get("calculations", [])
        ],
        "validation": dict(response.get("validation") or {}),
        "revisions": int(details.get("revisions", 0)),
        "draft": draft.get("text") if details.get("revisions") else None,
        "arm": result.get("arm"),
        "assignment": result.get("assignment"),
        "models": tokens,
        "cost_usd": cost,
        "cached": bool(response.get("cached")),
        "canary": canary,
        "retry_of": retry_of,
    }


class ExchangeLog:
    """The newest exchanges by request id, in the process's memory."""

    def __init__(self, size: int = MAX_EXCHANGES) -> None:
        self.size = size
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._claimed: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def add(self, exchange: dict[str, Any]) -> None:
        with self._lock:
            self._items[exchange["request_id"]] = exchange
            self._items.move_to_end(exchange["request_id"])
            while len(self._items) > self.size:
                gone, _ = self._items.popitem(last=False)
                self._claimed = {claim for claim in self._claimed if claim[0] != gone}

    def get(self, request_id: str | None) -> dict[str, Any] | None:
        with self._lock:
            return self._items.get(request_id) if request_id else None

    def claim(self, request_id: str, what: str) -> bool:
        """True the first time `what` (such as a rating's reward) is claimed for an exchange
        the log holds, so a repeated request counts once."""
        with self._lock:
            if request_id not in self._items or (request_id, what) in self._claimed:
                return False
            self._claimed.add((request_id, what))
            return True
