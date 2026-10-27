"""The answer bandit: ε-greedy and UCB1 learn the better arm; replays bound them."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from copilot.answer.bandit import ARMS, ArmChooser, EpsilonGreedy, reward
from copilot.eval import bandit


def test_the_arms_name_their_roles_and_settings() -> None:
    assert ARMS["strong"].role == "strong"
    assert ARMS["strong-low"].settings == {"reasoning_effort": "low"}
    assert ARMS["fast"].role == "fast"


def test_reward_takes_lambda_dollars_from_a_correct_answer() -> None:
    assert reward(1.0, 0.002, 100.0) == pytest.approx(0.8)
    assert reward(0.0, 0.0, 100.0) == 0.0


def test_epsilon_greedy_tries_every_arm_then_exploits_and_keeps_its_state() -> None:
    policy = EpsilonGreedy(["a", "b"], epsilon0=0.0)
    rng = random.Random(0)

    first = policy.choose(rng)
    policy.update(first, 0.0)
    second = policy.choose(rng)
    policy.update(second, 1.0)

    assert (first, second) == ("a", "b")
    assert policy.choose(rng) == "b"
    again = EpsilonGreedy.from_state(policy.state())
    assert again.state() == policy.state()
    assert again.choose(rng) == "b"


def test_epsilon_decays_with_the_steps() -> None:
    policy = EpsilonGreedy(["a"], epsilon0=1.0, tau=10.0)
    for _ in range(10):
        policy.update("a", 1.0)

    assert policy.epsilon() == pytest.approx(0.5)


def test_a_replay_puts_learners_between_the_fixed_arms_and_the_oracle() -> None:
    rng = np.random.default_rng(0)
    rewards = np.stack([rng.binomial(1, 0.3, 200), rng.binomial(1, 0.8, 200)], axis=1).astype(float)

    limits = bandit.bounds(rewards, ["weak", "good"])
    greedy = bandit.replay("greedy", lambda: bandit.Greedy(2), rewards, orders=50)
    ucb = bandit.replay("ucb1", lambda: bandit.UCB1(2), rewards, orders=50)
    fixed = bandit.replay("fixed", lambda: bandit.Fixed(1), rewards, orders=5)

    assert limits["fixed:weak"] < greedy.mean < limits["oracle"]
    assert greedy.shares[1] > 0.7
    assert ucb.shares[1] > 0.6
    assert fixed.mean == pytest.approx(limits["fixed:good"])
    assert fixed.shares == (0.0, 1.0)


def test_an_arm_chooser_keeps_its_state_in_a_file(tmp_path: Path) -> None:
    path = tmp_path / "bandit" / "answer-arms.json"
    chooser = ArmChooser(path, seed=0)

    first = chooser.choose()
    chooser.update(first.name, 1.0)
    again = ArmChooser(path, seed=0)

    assert first.name == "strong"  # every arm is tried once, in order
    assert again.policy.counts == {"strong": 1}
    assert again.choose().name == "strong-low"
    assert not path.with_suffix(".tmp").exists()
