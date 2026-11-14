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
`copilot.eval.bandit` replays it over judged answers.

Each answer's arm comes as a `Choice`: the arm, why it was chosen, and the client that
calls it.

- **On one machine,** with `FRC_ANSWER_POLICY=epsilon-greedy`, an `ArmChooser` picks each
  answer's arm and keeps its state in a file.
- **Online** (step 9.3, ADR-0036), an `OnlineChooser` flips a coin between the fixed arm
  (the control) and the policy. Its arms run on a paid client, the arms' counts and reward
  sums live in a store every instance shares (Firestore in the deployment), and at its
  daily cap it chooses nothing, so the answer takes the fixed path.
- **A second answer** to the same question (`avoid`, the first answer's arm) gets another
  arm at random, from either chooser.
"""

from __future__ import annotations

import json
import os
import random
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal, Protocol

from copilot.llm import LLMClient, ModelRole
from copilot.llm.fallback import SpendStore, utc_today
from copilot.logs import get_logger

log = get_logger(__name__)

FIXED = "strong"  # the arm the copilot answers with when no bandit chooses


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


Assignment = Literal["policy", "control", "retry"]


@dataclass(frozen=True, slots=True)
class Choice:
    """An answer's arm, why it has it, and the client that calls it.

    `assignment` is `policy` when the bandit chose the arm, `control` when the coin sent the
    answer to the fixed arm, and `retry` for a second answer. `llm` is None when the arm runs
    on the doc agent's own client; the online bandit's arms run on a paid client.
    """

    arm: Arm
    assignment: Assignment
    llm: LLMClient | None = None


class ArmPolicy(Protocol):
    """What the doc agent asks for each answer's arm; None means the fixed path."""

    def choose(self, avoid: str | None = None) -> Choice | None: ...


def other_arm(avoid: str, rng: random.Random, arms: Sequence[str] = tuple(ARMS)) -> Arm:
    """An arm other than `avoid`, at random, for a second answer to the same question."""
    others = [name for name in arms if name != avoid] or list(arms)
    return ARMS[rng.choice(others)]


class ArmChooser:
    """`EpsilonGreedy` over `ARMS`, its state kept in a JSON file, for choosing answers on
    one machine."""

    def __init__(self, path: Path, arms: Sequence[str] = tuple(ARMS), seed: int | None = None):
        self.path = path
        self._lock = threading.Lock()
        self._rng = random.Random(seed)
        if path.exists():
            self.policy = EpsilonGreedy.from_state(json.loads(path.read_text(encoding="utf-8")))
        else:
            self.policy = EpsilonGreedy(list(arms))

    def choose(self, avoid: str | None = None) -> Choice:
        with self._lock:
            if avoid is not None:
                return Choice(other_arm(avoid, self._rng, self.policy.arms), "retry")
            return Choice(ARMS[self.policy.choose(self._rng)], "policy")

    def update(self, arm: str, value: float) -> None:
        """Count one reward for `arm`, and save the state (written whole, then swapped in)."""
        with self._lock:
            self.policy.update(arm, value)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.policy.state(), indent=2), encoding="utf-8")
            os.replace(temporary, self.path)


class ArmStats(Protocol):
    """Each arm's number of rewards and their sum, shared by everything that chooses."""

    def read(self) -> tuple[dict[str, int], dict[str, float]]: ...
    def add(self, arm: str, value: float) -> None: ...


class MemoryArmStats:
    """Arm statistics kept in the process, for tests and for an API on one machine."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.sums: dict[str, float] = {}
        self._lock = threading.Lock()

    def read(self) -> tuple[dict[str, int], dict[str, float]]:
        with self._lock:
            return dict(self.counts), dict(self.sums)

    def add(self, arm: str, value: float) -> None:
        with self._lock:
            self.counts[arm] = self.counts.get(arm, 0) + 1
            self.sums[arm] = self.sums.get(arm, 0.0) + value


class OnlineChooser:
    """The answer bandit online (ADR-0036); see the module docstring.

    Each choice first checks the day's spend against `cap_usd`. Under it, a coin flip with
    `control_share` sends the answer to the fixed arm; otherwise ε-greedy chooses from the
    shared statistics, with ε = `epsilon0` / (1 + t / `tau`) after t rewards. At the cap, or
    when the spend or the statistics can't be read, it chooses nothing: an unknown total
    isn't under the cap, as for the paid fallback (ADR-0033).
    """

    def __init__(
        self,
        stats: ArmStats,
        spend: SpendStore,
        cap_usd: float,
        llm: LLMClient,
        *,
        control_share: float = 0.5,
        epsilon0: float = 0.2,
        tau: float = 50.0,
        arms: Sequence[str] = tuple(ARMS),
        seed: int | None = None,
        today: Callable[[], date] = utc_today,
    ) -> None:
        self.stats = stats
        self.spend = spend
        self.cap_usd = cap_usd
        self.llm = llm
        self.control_share = control_share
        self.epsilon0 = epsilon0
        self.tau = tau
        self.arms = list(arms)
        self._today = today
        self._rng = random.Random(seed)
        self._lock = threading.Lock()

    def under_cap(self) -> bool:
        """Whether today's spend is known and below the cap."""
        try:
            spent = self.spend.spent(self._today())
        except Exception as exc:  # any failure means an unknown total
            log.warning("bandit.unknown_spend", error=type(exc).__name__)
            return False
        if spent >= self.cap_usd:
            log.info("bandit.cap_reached", spent_usd=round(spent, 4))
            return False
        return True

    def policy(self) -> EpsilonGreedy:
        """ε-greedy as the shared statistics stand now."""
        counts, sums = self.stats.read()
        tried = {arm: count for arm, count in counts.items() if count > 0 and arm in self.arms}
        return EpsilonGreedy(
            self.arms,
            epsilon0=self.epsilon0,
            tau=self.tau,
            counts=tried,
            means={arm: sums.get(arm, 0.0) / count for arm, count in tried.items()},
            steps=sum(tried.values()),
        )

    def choose(self, avoid: str | None = None) -> Choice | None:
        if not self.under_cap():
            return None
        if avoid is not None:
            with self._lock:
                return Choice(other_arm(avoid, self._rng, self.arms), "retry", self.llm)
        with self._lock:
            control = self._rng.random() < self.control_share
        if control:
            return Choice(ARMS[FIXED], "control", self.llm)
        try:
            policy = self.policy()
        except Exception as exc:  # the statistics can't be read: take the fixed path
            log.warning("bandit.unknown_state", error=type(exc).__name__)
            return None
        with self._lock:
            return Choice(ARMS[policy.choose(self._rng)], "policy", self.llm)

    def reward(self, arm: str, value: float) -> None:
        """Count one reward for `arm`, whichever group its answer was in."""
        self.stats.add(arm, value)
