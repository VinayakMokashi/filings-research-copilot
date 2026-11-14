"""The answer bandit's side of the API (step 9.3, ADR-0036): what it logs, judges and rewards."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import Any

from copilot.answer.bandit import MemoryArmStats, OnlineChooser
from copilot.api.bandit import MemoryBanditLog, OnlineBandit
from copilot.llm import FakeLLM, LLMError, Message, ModelRole
from copilot.llm.fallback import MemorySpend

DAY = date(2026, 11, 16)
PASS = json.dumps({"sentences": [{"n": 1, "supported": True, "supporting": [1]}]})
FAIL = json.dumps({"sentences": [{"n": 1, "supported": False, "supporting": []}]})
SOURCE = {"number": 1, "label": "3M, PDF page 60", "text": "Capex was $1,577 million."}


def exchange(**fields: Any) -> dict[str, Any]:
    return {
        "request_id": "r1",
        "arm": "fast",
        "assignment": "policy",
        "route": "doc",
        "kind": "doc",
        "text": "Capex was $1,577 million [1].",
        "answered": True,
        "sources": [SOURCE],
        "calculations": [],
        "cost_usd": 0.005,
        "cached": False,
        "canary": False,
        "retry_of": None,
    } | fields


def bandit(judge: FakeLLM, *, share: float = 1.0, spent: float = 0.0) -> OnlineBandit:
    spend = MemorySpend()
    spend.add(DAY, spent)
    chooser = OnlineChooser(MemoryArmStats(), spend, 0.25, FakeLLM([]), today=lambda: DAY)
    return OnlineBandit(chooser, judge, MemoryBanditLog(), judge_share=share, seed=0)


def rewards(online: OnlineBandit) -> tuple[dict[str, int], dict[str, float]]:
    return online.chooser.stats.read()


def records(online: OnlineBandit) -> dict[str, dict[str, Any]]:
    log = online.log
    assert isinstance(log, MemoryBanditLog)
    return log.records


def test_a_judged_answer_rewards_its_arm_and_is_logged() -> None:
    passed, failed = bandit(FakeLLM([PASS])), bandit(FakeLLM([FAIL]))

    good = passed.after_answer(exchange())
    bad = failed.after_answer(exchange(arm="strong", assignment="control"))

    assert good is not None
    assert (good["judged"], good["faithful"], good["reward"]) == (True, True, 1.0)
    assert bad is not None
    assert bad["reward"] == 0.0
    assert rewards(passed) == ({"fast": 1}, {"fast": 1.0})
    assert rewards(failed) == ({"strong": 1}, {"strong": 0.0})
    record = records(passed)["r1"]
    assert (record["arm"], record["assignment"], record["judge"]) == ("fast", "policy", 1.0)
    assert record["judge_cost_usd"] is None  # the fake judge's model has no price


def test_a_refusal_earns_nothing_without_a_judges_call() -> None:
    judge = FakeLLM([])
    online = bandit(judge)

    event = online.after_answer(exchange(text="The filings I searched don't contain it."))

    assert event is not None
    assert event["reward"] == 0.0
    assert judge.calls == []  # nothing cited, nothing to check


def test_only_fresh_answers_the_bandit_chose_or_controlled_are_learned_from() -> None:
    judge = FakeLLM([PASS])
    online = bandit(judge)

    assert online.after_answer(exchange(arm=None, assignment=None)) is None  # the fixed path
    assert online.after_answer(exchange(cached=True)) is None
    retry = online.after_answer(exchange(request_id="r2", assignment="retry", retry_of="r1"))

    assert retry == {
        "type": "event",
        "event": "reward",
        "arm": "fast",
        "assignment": "retry",
        "judged": False,
    }
    assert records(online)["r2"]["retry_of"] == "r1"  # logged, for its cost
    assert judge.calls == []
    assert rewards(online) == ({}, {})


def test_the_judge_samples_visitors_answers_but_every_canary_answer() -> None:
    judge = FakeLLM([PASS])
    online = bandit(judge, share=0.0)

    visitor = online.after_answer(exchange())
    canary = online.after_answer(exchange(request_id="r2", canary=True))

    assert visitor is not None
    assert visitor["judged"] is False
    assert canary is not None
    assert canary["judged"] is True
    assert len(judge.calls) == 1


def test_at_the_cap_the_judge_is_not_called() -> None:
    judge = FakeLLM([PASS])
    online = bandit(judge, spent=0.25)

    event = online.after_answer(exchange(canary=True))

    assert event is not None
    assert event["judged"] is False
    assert judge.calls == []


def test_a_judge_that_fails_or_cant_be_read_rewards_nothing() -> None:
    def down(messages: Sequence[Message], role: ModelRole) -> str:
        raise LLMError("The fast model call failed: APIConnectionError")

    failed, unreadable = bandit(FakeLLM(down)), bandit(FakeLLM(["not JSON"]))

    assert failed.after_answer(exchange()) == exchange_event(judged=False)
    assert unreadable.after_answer(exchange()) == exchange_event(judged=False)
    assert rewards(failed) == rewards(unreadable) == ({}, {})


def exchange_event(**fields: Any) -> dict[str, Any]:
    return {"type": "event", "event": "reward", "arm": "fast", "assignment": "policy"} | fields


def test_a_rating_rewards_the_bandits_answers_and_is_logged_for_a_retry() -> None:
    online = bandit(FakeLLM([]))

    up = online.thumbs(exchange(), "up")
    down = online.thumbs(exchange(request_id="r2", arm="strong", assignment="control"), "down")
    retry = online.thumbs(exchange(request_id="r3", assignment="retry"), "up")
    fixed = online.thumbs(exchange(request_id="r4", arm=None), "up")

    assert (up, down, retry, fixed) == (True, True, False, False)
    assert rewards(online) == ({"fast": 1, "strong": 1}, {"fast": 1.0, "strong": 0.0})
    assert records(online)["r3"] == {"thumbs": 1.0}
    assert "r4" not in records(online)
