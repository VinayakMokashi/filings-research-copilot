"""The answer bandit: ε-greedy and UCB1 learn the better arm; replays bound them; online,
a coin flip, shared statistics and a daily cap."""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from copilot.answer.bandit import (
    ARMS,
    ArmChooser,
    EpsilonGreedy,
    MemoryArmStats,
    OnlineChooser,
    other_arm,
    reward,
)
from copilot.eval import bandit
from copilot.llm import FakeLLM
from copilot.llm.fallback import MemorySpend


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
    chooser.update(first.arm.name, 1.0)
    again = ArmChooser(path, seed=0)

    assert (first.arm.name, first.assignment, first.llm) == ("strong", "policy", None)
    assert again.policy.counts == {"strong": 1}  # every arm is tried once, in order
    assert again.choose().arm.name == "strong-low"
    assert not path.with_suffix(".tmp").exists()


DAY = date(2026, 11, 16)


def online(stats: MemoryArmStats | None = None, **settings: object) -> OnlineChooser:
    options: dict[str, object] = {"seed": 0, "today": lambda: DAY} | settings
    return OnlineChooser(
        stats or MemoryArmStats(),
        MemorySpend(),
        0.25,
        FakeLLM([]),
        **options,  # type: ignore[arg-type]
    )


def test_other_arm_never_returns_the_arm_to_avoid() -> None:
    rng = random.Random(0)

    assert {other_arm("strong", rng).name for _ in range(50)} == {"strong-low", "fast"}
    assert other_arm("fast", rng, ["fast"]).name == "fast"  # nothing else to take


def test_a_second_answer_from_the_file_chooser_takes_another_arm(tmp_path: Path) -> None:
    choice = ArmChooser(tmp_path / "arms.json", seed=0).choose(avoid="strong")

    assert choice.assignment == "retry"
    assert choice.arm.name in ("strong-low", "fast")


def test_the_online_chooser_flips_a_coin_between_the_fixed_arm_and_the_policy() -> None:
    control = online(control_share=1.0).choose()
    chooser = online(control_share=0.0)
    first = chooser.choose()
    chooser.reward("strong", 1.0)

    assert control is not None
    assert first is not None
    assert (control.arm.name, control.assignment) == ("strong", "control")
    assert control.llm is not None  # the arms run on the paid client
    assert (first.arm.name, first.assignment) == ("strong", "policy")  # untried arms first
    second = chooser.choose()
    assert second is not None
    assert second.arm.name == "strong-low"


def test_the_coin_sends_about_its_share_to_the_fixed_arm() -> None:
    chooser = online(control_share=0.5)

    groups = [choice.assignment for choice in (chooser.choose() for _ in range(400)) if choice]

    assert 160 < groups.count("control") < 240


def test_rewards_from_every_group_teach_the_policy() -> None:
    stats = MemoryArmStats()
    for arm, value in (("strong", 0.0), ("strong-low", 1.0), ("fast", 0.0), ("strong", 1.0)):
        stats.add(arm, value)

    chooser = online(stats, control_share=0.0, epsilon0=0.0)
    policy = chooser.policy()

    assert policy.means == {"strong": 0.5, "strong-low": 1.0, "fast": 0.0}
    assert policy.steps == 4
    choice = chooser.choose()
    assert choice is not None
    assert choice.arm.name == "strong-low"


def test_epsilon_starts_at_its_setting_and_halves_after_tau_rewards() -> None:
    stats = MemoryArmStats()
    for _ in range(50):
        stats.add("strong", 1.0)

    assert online().policy().epsilon() == pytest.approx(0.2)
    assert online(stats).policy().epsilon() == pytest.approx(0.1)


def test_at_its_cap_or_with_an_unknown_spend_the_online_chooser_chooses_nothing() -> None:
    spend = MemorySpend()
    spend.add(DAY, 0.25)
    capped = OnlineChooser(MemoryArmStats(), spend, 0.25, FakeLLM([]), today=lambda: DAY)

    class Unreadable:
        def spent(self, day: date) -> float:
            raise ConnectionError("Firestore unreachable")

        def add(self, day: date, usd: float) -> None:
            raise ConnectionError("Firestore unreachable")

    unknown = OnlineChooser(MemoryArmStats(), Unreadable(), 0.25, FakeLLM([]))

    assert capped.choose() is None
    assert capped.choose(avoid="strong") is None
    assert unknown.choose() is None
    assert spend.spent(date(2026, 11, 17)) == 0.0  # a new day starts under the cap


def test_a_second_answer_from_the_online_chooser_takes_another_arm_on_the_paid_client() -> None:
    chooser = online()

    choice = chooser.choose(avoid="strong")

    assert choice is not None
    assert choice.assignment == "retry"
    assert choice.arm.name != "strong"
    assert choice.llm is chooser.llm
