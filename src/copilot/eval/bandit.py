"""Replaying a bandit over judged answers, offline (step 7.5).

Every arm answered every dev question from the same sources, and the judge graded each
answer, so the whole table of rewards is known: one row a question, one column an arm
(`copilot.answer.bandit.reward`). An offline replay shows a policy the questions in a random
order and, at each, reveals only the reward of the arm it chose, as a live bandit would see
it. Over many orders, its average reward a question sits between each fixed arm's (no
learning, no exploring) and the oracle's (the best arm for every question, known in
hindsight), which bound what any policy can do on these questions.

Policies: `Fixed` (always one arm), ε-greedy with ε decaying (`copilot.answer.bandit`), and
UCB1 (Auer et al., 2002), which explores the arms it is least sure of instead of at random.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from copilot.answer.bandit import EpsilonGreedy


class Policy(Protocol):
    def choose(self, rng: random.Random) -> int: ...

    def update(self, arm: int, value: float) -> None: ...


@dataclass
class Fixed:
    """Always the same arm."""

    arm: int

    def choose(self, rng: random.Random) -> int:
        return self.arm

    def update(self, arm: int, value: float) -> None:
        return None


class Greedy:
    """`EpsilonGreedy` over arm numbers."""

    def __init__(self, arms: int, epsilon0: float = 1.0, tau: float = 10.0) -> None:
        self._policy = EpsilonGreedy([str(arm) for arm in range(arms)], epsilon0, tau)

    def choose(self, rng: random.Random) -> int:
        return int(self._policy.choose(rng))

    def update(self, arm: int, value: float) -> None:
        self._policy.update(str(arm), value)


class UCB1:
    """Each arm once, then the arm with the highest mean plus c * sqrt(2 ln t / n)."""

    def __init__(self, arms: int, c: float = 1.0) -> None:
        self.c = c
        self.counts = [0] * arms
        self.means = [0.0] * arms

    def choose(self, rng: random.Random) -> int:
        for arm, count in enumerate(self.counts):
            if count == 0:
                return arm
        total = sum(self.counts)
        bonus = [self.c * math.sqrt(2 * math.log(total) / n) for n in self.counts]
        values = [mean + extra for mean, extra in zip(self.means, bonus, strict=True)]
        return max(range(len(values)), key=lambda arm: values[arm])

    def update(self, arm: int, value: float) -> None:
        self.counts[arm] += 1
        self.means[arm] += (value - self.means[arm]) / self.counts[arm]


@dataclass(frozen=True, slots=True)
class Replay:
    """A policy's average reward a question over the replayed orders, and its arm shares."""

    policy: str
    mean: float
    low: float  # 2.5th percentile over orders
    high: float  # 97.5th percentile over orders
    shares: tuple[float, ...]


def replay(
    name: str,
    make: Callable[[], Policy],
    rewards: NDArray[np.float64],
    orders: int = 1000,
    seed: int = 0,
) -> Replay:
    """`make()`'s policy over `orders` random orders of the questions (rows of `rewards`)."""
    rng = random.Random(seed)
    questions, arms = rewards.shape
    means = []
    chosen = np.zeros(arms)
    for _ in range(orders):
        policy = make()
        order = list(range(questions))
        rng.shuffle(order)
        total = 0.0
        for question in order:
            arm = policy.choose(rng)
            value = float(rewards[question, arm])
            policy.update(arm, value)
            total += value
            chosen[arm] += 1
        means.append(total / questions)
    shares = tuple(float(share) for share in chosen / chosen.sum())
    low, high = np.percentile(means, [2.5, 97.5])
    return Replay(name, float(np.mean(means)), float(low), float(high), shares)


def bounds(rewards: NDArray[np.float64], names: Sequence[str]) -> dict[str, float]:
    """Each fixed arm's average reward, and the oracle's (each question's best arm)."""
    fixed = {f"fixed:{name}": float(rewards[:, arm].mean()) for arm, name in enumerate(names)}
    return fixed | {"oracle": float(rewards.max(axis=1).mean())}
