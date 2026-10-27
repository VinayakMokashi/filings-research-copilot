"""Replay answer-model bandits over the arms' judged dev answers, offline (step 7.5).

Reads each arm's judged run (eval/results/correctness/<run>--<judge>/dev/items.jsonl) and its
answers' tokens (data/processed/answers/<run>/dev/answers.jsonl), prices each answer with
the gateway's token prices, and builds, for each λ, the table of rewards: 1 for a correct
answer, 0 otherwise, less λ times its cost in dollars (`copilot.answer.bandit.reward`).
Then it replays ε-greedy and UCB1 over many random orders of the questions
(`copilot.eval.bandit`), beside each fixed arm and the oracle.

Writes eval/results/bandit/<name>/dev/summary.json and summary.md.

Usage:
  uv run poe replay-bandit --arms strong=arm-strong,strong-low=arm-strong-low,fast=arm-fast \\
      --lambdas 0,100,300 --name answer-arms
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from copilot.answer.bandit import reward
from copilot.config import get_settings
from copilot.eval import bandit
from copilot.eval.report import RESULTS_DIR
from copilot.llm.gateway import token_cost


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {record["id"]: record for record in records}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--arms", required=True, help="name=run pairs, comma-separated")
    parser.add_argument("--judge", default="qwen-3.8-27b-p2", help="the judge's run suffix")
    parser.add_argument("--lambdas", default="0,100,300", help="dollar penalties, comma-separated")
    parser.add_argument("--orders", type=int, default=2000, help="random orders to replay")
    parser.add_argument("--name", default="answer-arms")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    settings = get_settings()
    arms = [pair.split("=", 1) for pair in args.arms.split(",")]
    names = [name for name, _ in arms]

    correct: dict[str, dict[str, float]] = {}
    cost: dict[str, dict[str, float]] = {}
    models: dict[str, str] = {}
    for name, run in arms:
        judged = read_jsonl(
            args.results_dir / "correctness" / f"{run}--{args.judge}" / "dev" / "items.jsonl"
        )
        answers = read_jsonl(
            settings.data_dir / "processed" / "answers" / run / "dev" / "answers.jsonl"
        )
        correct[name] = {qid: float(item["correct"]) for qid, item in judged.items()}
        cost[name] = {}
        for qid, answer in answers.items():
            price = token_cost(
                answer["model"], answer["prompt_tokens"], answer["completion_tokens"]
            )
            cost[name][qid] = price if price is not None else 0.0
        models[name] = next(iter(answers.values()))["model"]
    ids = sorted(set.intersection(*(set(correct[n]) & set(cost[n]) for n in names)))

    per_arm = {
        name: {
            "model": models[name],
            "correct": round(float(np.mean([correct[name][q] for q in ids])), 4),
            "cost_usd": round(float(np.mean([cost[name][q] for q in ids])), 6),
        }
        for name in names
    }
    results: list[dict[str, Any]] = []
    for lam in (float(value) for value in args.lambdas.split(",")):
        table = np.array(
            [[reward(correct[n][q], cost[n][q], lam) for n in names] for q in ids], dtype=float
        )
        limits = bandit.bounds(table, names)
        learners = [
            bandit.replay("epsilon-greedy", lambda: bandit.Greedy(len(names)), table, args.orders),
            bandit.replay("ucb1", lambda: bandit.UCB1(len(names)), table, args.orders),
        ]
        best = max(names, key=lambda n: limits[f"fixed:{n}"])
        results.append(
            {
                "lambda": lam,
                "fixed": {n: round(limits[f"fixed:{n}"], 4) for n in names},
                "oracle": round(limits["oracle"], 4),
                "best_fixed": best,
                "learners": [
                    {
                        "policy": r.policy,
                        "mean": round(r.mean, 4),
                        "low": round(r.low, 4),
                        "high": round(r.high, 4),
                        "shares": dict(zip(names, (round(s, 3) for s in r.shares), strict=True)),
                        "regret_vs_best_fixed": round(limits[f"fixed:{best}"] - r.mean, 4),
                    }
                    for r in learners
                ],
            }
        )

    summary = {
        "suite": "bandit",
        "run": args.name,
        "split": "dev",
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions": len(ids),
        "orders": args.orders,
        "judge": args.judge,
        "arms": dict(arms),
        "per_arm": per_arm,
        "results": results,
    }
    directory = args.results_dir / "bandit" / args.name / "dev"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        f"# bandit: {args.name} (dev)",
        "",
        f"{len(ids)} questions, {args.orders:,} random orders, judge {args.judge}.",
        "",
        "| Arm | Model | Correct | Cost a question |",
        "|---|---|---|---|",
        *(
            f"| {n} | {per_arm[n]['model']} | {per_arm[n]['correct']:.2f} | "
            f"${per_arm[n]['cost_usd']:.5f} |"
            for n in names
        ),
    ]
    for result in results:
        lines += [
            "",
            f"## λ = {result['lambda']:g} (reward = correct - λ * dollars)",
            "",
            "| Policy | Average reward a question | Spread over orders | Arm shares |",
            "|---|---|---|---|",
            *(f"| fixed: {n} | {v:.4f} | | |" for n, v in result["fixed"].items()),
            f"| oracle | {result['oracle']:.4f} | | |",
            *(
                f"| {r['policy']} | {r['mean']:.4f} | {r['low']:.4f} to {r['high']:.4f} | "
                + ", ".join(f"{k} {v:.2f}" for k, v in r["shares"].items())
                + " |"
                for r in result["learners"]
            ),
        ]
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for result in results:
        scores = ", ".join(f"{r['policy']} {r['mean']:.4f}" for r in result["learners"])
        print(f"lambda {result['lambda']:g}: best fixed {result['best_fixed']}, {scores}")
    print(f"Wrote {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
