"""A run's spending cap: the ledger its processes share, the gateway's check, no retries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from copilot.config import Settings
from copilot.llm import BudgetSpentError, LLMGateway, LLMResponse, user
from copilot.llm.budget import RunBudget, read_ledger, spent_by_model
from copilot.llm.pacing import PacedLLM


def response(cost_usd: float | None, model: str = "cerebras/gpt-oss-120b") -> LLMResponse:
    return LLMResponse(text="ok", role="strong", model=model, latency_s=0.1, cost_usd=cost_usd)


def test_the_ledger_adds_up_calls_and_refuses_once_the_cap_is_reached(tmp_path: Path) -> None:
    budget = RunBudget(tmp_path / "ledger.jsonl", cap_usd=0.01)

    budget.check()  # nothing spent yet
    budget.add(response(0.006))
    budget.check()  # $0.006 is under the cap
    budget.add(response(0.006))

    assert budget.spent() == pytest.approx(0.012)
    with pytest.raises(BudgetSpentError, match=r"budget of \$0.01 is spent"):
        budget.check()


def test_processes_share_one_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "night" / "ledger.jsonl"
    answers, judge = RunBudget(ledger, cap_usd=0.30), RunBudget(ledger, cap_usd=0.40)

    answers.add(response(0.31))

    with pytest.raises(BudgetSpentError):
        answers.check()
    judge.check()  # a later step's larger share of the same ledger still has room
    assert judge.spent() == pytest.approx(0.31)


def test_an_unknown_price_counts_a_cent_and_a_cut_line_is_skipped(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    budget = RunBudget(ledger, cap_usd=1.0)

    assert budget.add(response(None)) == 0.01
    budget.add(response(0.002, model="groq/openai/gpt-oss-20b"))
    with ledger.open("a", encoding="utf-8") as out:
        out.write('{"usd": 0.5, "mod')  # a process killed mid-write

    assert len(read_ledger(ledger)) == 2
    assert spent_by_model(ledger) == {
        "cerebras/gpt-oss-120b": 0.01,
        "groq/openai/gpt-oss-20b": 0.002,
    }


def test_the_gateway_counts_its_calls_and_stops_at_the_cap(
    settings: Settings, tmp_path: Path
) -> None:
    ledger = tmp_path / "ledger.jsonl"
    capped = settings.model_copy(update={"llm_budget_usd": 1e-9, "llm_budget_file": ledger})
    gateway = LLMGateway(capped)

    gateway.complete([user("hi")], mock_response="ok")  # nothing spent before it

    calls = read_ledger(ledger)
    assert [call["model"] for call in calls] == [settings.llm_fast_model]
    assert calls[0]["usd"] > 0
    with pytest.raises(BudgetSpentError):
        gateway.complete([user("hi again")], mock_response="ok")
    assert len(read_ledger(ledger)) == 1  # the refused call reached no model


def test_a_cap_needs_a_ledger(settings: Settings) -> None:
    with pytest.raises(ValueError, match="FRC_LLM_BUDGET_FILE"):
        LLMGateway(settings.model_copy(update={"llm_budget_usd": 0.4}))


class _Spent:
    calls = 0

    def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        raise BudgetSpentError("The run's budget of $0.40 is spent ($0.4012).")

    async def acomplete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        raise NotImplementedError


def test_a_spent_budget_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Spent()
    monkeypatch.setattr("copilot.llm.pacing.time.sleep", lambda s: pytest.fail("it waited"))

    with pytest.raises(BudgetSpentError) as raised:
        PacedLLM(client).complete([user("hi")])

    assert client.calls == 1
    assert raised.value.rate_limited  # the run stops as on a spent quota
