"""The answer bandit's side of the API (step 9.3, ADR-0036): a log of every answer it paid
for, the judge on a sample of them, and rewards from the judge and from ratings.

- **What it learns from.** Only fresh answers an arm wrote as the bandit's choice or as the
  coin's control (`policy`, `control`). A second answer (`retry`) follows a thumbs down,
  so its question is harder than the arm's usual one; an answer from the cache wasn't
  written for its request. Both are logged, and reward nothing.
- **The judge** is the nightly evaluation's faithfulness check (prompt 1) on the paid
  `fast` model, with reasoning off (ADR-0024). It scores `judge_share` of the visitors'
  answers, chosen at random, and every canary answer, while the day's spend is under the
  cap. Its reward is 1 when every cited sentence is supported and 0 otherwise, a refusal
  included, since it cites nothing. A reply it can't read rewards nothing.
- **A rating** is a reward of 1 for a thumbs up and 0 for a thumbs down.

A reward is the answer's quality alone: the cap bounds the money, and each answer's cost is
logged, so the report can weigh it too.
"""

from __future__ import annotations

import random
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from copilot.answer.bandit import OnlineChooser
from copilot.eval.faithfulness import Faithfulness, check
from copilot.llm import LLMClient, LLMError
from copilot.llm.gateway import token_cost
from copilot.logs import get_logger

log = get_logger(__name__)

LEARNS_FROM = ("policy", "control")


class BanditLog(Protocol):
    """One record per answer an arm wrote, with its rewards merged in as they come."""

    def start(self, request_id: str, record: dict[str, Any]) -> None: ...
    def update(self, request_id: str, fields: dict[str, Any]) -> None: ...


class MemoryBanditLog:
    """The bandit's log in the process, for tests and for an API on one machine."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, request_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self.records[request_id] = dict(record)

    def update(self, request_id: str, fields: dict[str, Any]) -> None:
        with self._lock:
            self.records.setdefault(request_id, {}).update(fields)


class OnlineBandit:
    """Logs, judges and rewards the answers `chooser`'s arms write; see the module docstring."""

    def __init__(
        self,
        chooser: OnlineChooser,
        judge: LLMClient,
        log_: BanditLog,
        *,
        judge_share: float = 0.5,
        seed: int | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.chooser = chooser
        self.judge = judge
        self.log = log_
        self.judge_share = judge_share
        self._now = now
        self._rng = random.Random(seed)
        self._lock = threading.Lock()

    def after_answer(self, exchange: Mapping[str, Any]) -> dict[str, Any] | None:
        """Log an answer an arm wrote and, for a sample, judge it. Returns the data of the
        `reward` event the API sends before the stream ends, or None when no arm wrote it."""
        arm, assignment = exchange.get("arm"), exchange.get("assignment")
        if arm is None or exchange.get("cached"):
            return None
        request_id = str(exchange["request_id"])
        canary = bool(exchange.get("canary"))
        self.log.start(
            request_id,
            {
                "created": self._now(),
                "arm": arm,
                "assignment": assignment,
                "canary": canary,
                "route": exchange.get("route"),
                "kind": exchange.get("kind"),
                "answered": exchange.get("answered"),
                "cost_usd": exchange.get("cost_usd"),
                "retry_of": exchange.get("retry_of"),
            },
        )
        event = {"type": "event", "event": "reward", "arm": arm, "assignment": assignment}
        if assignment not in LEARNS_FROM:
            return event | {"judged": False}
        with self._lock:
            sampled = self._rng.random() < (1.0 if canary else self.judge_share)
        if not sampled or not self.chooser.under_cap():
            return event | {"judged": False}
        verdict = self._judge(exchange)
        if verdict is None:
            return event | {"judged": False}
        value = 1.0 if verdict.faithful else 0.0
        self.chooser.reward(str(arm), value)
        self.log.update(
            request_id,
            {
                "judge": value,
                "judge_cost_usd": token_cost(
                    verdict.model, verdict.prompt_tokens, verdict.completion_tokens
                ),
            },
        )
        return event | {"judged": True, "faithful": verdict.faithful, "reward": value}

    def thumbs(self, exchange: Mapping[str, Any], rating: str) -> bool:
        """Log a rating of an answer an arm wrote, and reward the arm when the answer is one
        the bandit learns from; whether it was rewarded."""
        arm = exchange.get("arm")
        if arm is None or exchange.get("cached"):
            return False
        value = 1.0 if rating == "up" else 0.0
        self.log.update(str(exchange["request_id"]), {"thumbs": value})
        if exchange.get("assignment") not in LEARNS_FROM:
            return False
        self.chooser.reward(str(arm), value)
        return True

    def _judge(self, exchange: Mapping[str, Any]) -> Faithfulness | None:
        sources = {
            int(source["number"]): (str(source["label"]), str(source["text"]))
            for source in exchange.get("sources", [])
        }
        calculations = [
            (str(calculation["id"]), str(calculation["expression"]), calculation.get("value"))
            for calculation in exchange.get("calculations", [])
        ]
        try:
            verdict = check(self.judge, str(exchange.get("text", "")), sources, calculations)
        except LLMError as exc:
            log.warning("bandit.judge_failed", error=type(exc).__name__)
            return None
        if verdict.error is not None:  # an unreadable reply: no reward either way
            log.warning("bandit.judge_unreadable")
            return None
        return verdict
