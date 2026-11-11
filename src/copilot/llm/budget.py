"""A spending cap for a batch run, shared by the run's processes (ADR-0034).

The nightly evaluation runs several scripts one after another (the copilot's answers, the
judges, the routing and SQL sets), each a process of its own, against one cap. Every call
that reaches a model adds its cost to a ledger file, one JSON line a call, and every call
first reads the ledger's total: once that reaches the cap, the call is refused with
`BudgetSpentError`, and the run stops with what it has. A step can be given a lower cap on the
same ledger than the night's, so that the steps after it still have a share left.

Calls answered from a disk cache never reach the gateway, so they cost nothing here. A call
whose price LiteLLM doesn't know counts as $0.01, as the paid fallback counts it (ADR-0033).
Calls already in flight when the cap is reached can pass it by one call's cost each.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from copilot.llm.base import BudgetSpentError, LLMResponse
from copilot.llm.fallback import UNKNOWN_COST_USD


def read_ledger(path: Path) -> list[dict[str, Any]]:
    """The ledger's calls; a line cut short by a kill is skipped."""
    if not path.exists():
        return []
    calls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            call = json.loads(line)
            call["usd"] = float(call["usd"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        calls.append(call)
    return calls


def spent_by_model(path: Path) -> dict[str, float]:
    """Dollars in the ledger by model, for a run's report."""
    totals: dict[str, float] = defaultdict(float)
    for call in read_ledger(path):
        totals[str(call.get("model", ""))] += call["usd"]
    return dict(totals)


class RunBudget:
    """A cap of `cap_usd` on the calls counted in the ledger at `path`; see the module docstring."""

    def __init__(self, path: Path, cap_usd: float) -> None:
        self.path = path
        self.cap_usd = cap_usd
        self._lock = threading.Lock()

    def spent(self) -> float:
        """Dollars counted so far, by every process that shares the ledger."""
        return float(sum(float(call["usd"]) for call in read_ledger(self.path)))

    def check(self) -> None:
        """Raise `BudgetSpentError` once the ledger's total has reached the cap."""
        spent = self.spent()
        if spent >= self.cap_usd:
            raise BudgetSpentError(
                f"The run's budget of ${self.cap_usd:.2f} is spent (${spent:.4f})."
            )

    def add(self, response: LLMResponse) -> float:
        """Count one call's cost, and return what was counted."""
        usd = UNKNOWN_COST_USD if response.cost_usd is None else response.cost_usd
        call = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "role": response.role,
            "model": response.model,
            "usd": usd,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as ledger:
                ledger.write(json.dumps(call) + "\n")
        return usd
