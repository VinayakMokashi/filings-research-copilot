"""Choosing the doc agent's answer model with a bandit (step 7.5).

Every answer call can go to one of a few model settings, the arms: gpt-oss-120b at its
default reasoning effort (the `strong` role, as the copilot answers now), the same model
reasoning less, which is cheaper and faster, or Qwen3.8 27B with reasoning off (the `fast`
role). Which one is worth its cost depends on what a right answer is worth against a dollar,
so an answer's reward is 1 when the judge counts it correct and 0 when not, minus λ times
its cost in dollars.

`EpsilonGreedy` learns which arm pays best from the rewards it is told: it tries each arm
once, then with probability ε picks an arm at random and otherwise the arm with the best
average reward so far, with ε decaying as it learns (ε_t = ε0 / (1 + t / τ)). Its counts and
averages are plain JSON, so they can be kept between processes. Offline,
`copilot.eval.bandit` replays it over judged answers. Online, with
`FRC_ANSWER_POLICY=epsilon-greedy`, an `ArmChooser` picks each answer's arm for the doc agent
and keeps its state in a file; the rewards are to come from the feedback Phase 9 collects,
through `ArmChooser.update`.
"""

from __future__ import annotations

import json
import os
import random
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from copilot.llm import ModelRole


@dataclass(frozen=True, slots=True)
class Arm:
    """One way to write an answer: a model role and the settings it is called with."""

    name: str
    role: ModelRole
    params: tuple[tuple[str, Any], ...] = ()

    @property
    def settings(self) -> dict[str, Any]:
        return dict(self.params)


ARMS: dict[str, Arm] = {
    arm.name: arm
    for arm in (
        Arm("strong", "strong"),
        Arm("strong-low", "strong", (("reasoning_effort", "low"),)),
        Arm("fast", "fast"),
    )
}


def reward(correct: float, cost_usd: float, lam: float) -> float:
    """1 for a correct answer, 0 otherwise, less λ dollars-worth of penalty for its cost."""
    return correct - lam * cost_usd


@dataclass
class EpsilonGreedy:
    """Sample-average ε-greedy over named arms, with ε decaying; see the module docstring."""

    arms: Sequence[str]
    epsilon0: float = 1.0
    tau: float = 10.0
    counts: dict[str, int] = field(default_factory=dict)
    means: dict[str, float] = field(default_factory=dict)
    steps: int = 0

    def epsilon(self) -> float:
        return self.epsilon0 / (1.0 + self.steps / self.tau)

    def choose(self, rng: random.Random) -> str:
        untried = [arm for arm in self.arms if self.counts.get(arm, 0) == 0]
        if untried:
            return untried[0]
        if rng.random() < self.epsilon():
            return rng.choice(list(self.arms))
        return max(self.arms, key=lambda arm: self.means[arm])  # ties: the first arm

    def update(self, arm: str, value: float) -> None:
        count = self.counts.get(arm, 0) + 1
        mean = self.means.get(arm, 0.0)
        self.counts[arm] = count
        self.means[arm] = mean + (value - mean) / count
        self.steps += 1

    def state(self) -> dict[str, Any]:
        return {
            "arms": list(self.arms),
            "epsilon0": self.epsilon0,
            "tau": self.tau,
            "counts": dict(self.counts),
            "means": dict(self.means),
            "steps": self.steps,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> EpsilonGreedy:
        return cls(
            arms=list(state["arms"]),
            epsilon0=float(state["epsilon0"]),
            tau=float(state["tau"]),
            counts={str(k): int(v) for k, v in state["counts"].items()},
            means={str(k): float(v) for k, v in state["means"].items()},
            steps=int(state["steps"]),
        )


class ArmChooser:
    """`EpsilonGreedy` over `ARMS`, its state kept in a JSON file, for choosing answers online."""

    def __init__(self, path: Path, arms: Sequence[str] = tuple(ARMS), seed: int | None = None):
        self.path = path
        self._lock = threading.Lock()
        self._rng = random.Random(seed)
        if path.exists():
            self.policy = EpsilonGreedy.from_state(json.loads(path.read_text(encoding="utf-8")))
        else:
            self.policy = EpsilonGreedy(list(arms))

    def choose(self) -> Arm:
        with self._lock:
            return ARMS[self.policy.choose(self._rng)]

    def update(self, arm: str, value: float) -> None:
        """Count one reward for `arm`, and save the state (written whole, then swapped in)."""
        with self._lock:
            self.policy.update(arm, value)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.policy.state(), indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
