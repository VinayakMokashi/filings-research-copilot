"""Latency and cost of the copilot's runs, read from their traces (step 6.5).

A trace file holds every event of each run (`copilot.agents.runner`). For each run that
reached its response, `read_runs` finds the route, the seconds from its first event to the
response, the milliseconds each node took (added up when a node ran twice, as the
validator can) and the tokens and dollars its model calls spent. `summarise` reports the
median, the 95th percentile and the slowest, by route and by node.

Runs stopped by an error or a spent quota have no response and are left out. Batch runs
pause to stay under the free tier's tokens a minute, and those pauses count, so a batch
trace measures throughput under the quota more than a single question's wait.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class RunTiming:
    run: str
    route: str
    seconds: float
    nodes: dict[str, float]  # milliseconds by node
    tokens: int
    cost_usd: float | None  # None when a model's price is unknown


def read_events(paths: Iterable[Path]) -> list[dict[str, Any]]:
    events = []
    for path in paths:
        with path.open(encoding="utf-8") as lines:
            events += [json.loads(line) for line in lines if line.strip()]
    return events


def read_runs(events: Iterable[dict[str, Any]]) -> list[RunTiming]:
    """Every run that reached its response, in the order the runs started."""
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[str(event.get("run"))].append(event)
    runs = []
    for run, items in by_run.items():
        response = next((e for e in items if e.get("type") == "response"), None)
        if response is None:
            continue
        nodes: dict[str, float] = defaultdict(float)
        tokens, costs = 0, []
        for event in items:
            if event.get("type") == "end":
                nodes[str(event["node"])] += float(event.get("ms") or 0.0)
            elif event.get("type") == "event" and event.get("event") == "usage":
                tokens += sum(sum(pair) for pair in event.get("tokens_by_model", {}).values())
                costs.append(event.get("cost_usd"))
        known = [cost for cost in costs if cost is not None]
        runs.append(
            RunTiming(
                run=run,
                route=str(response.get("route") or "unknown"),
                seconds=_seconds(items[0]["ts"], response["ts"]),
                nodes=dict(nodes),
                tokens=tokens,
                cost_usd=round(sum(known), 7) if len(known) == len(costs) else None,
            )
        )
    return runs


def _seconds(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def spread(values: Sequence[float]) -> dict[str, float | int]:
    """How many values, their median, 95th percentile and maximum."""
    array = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "p50": round(float(np.percentile(array, 50)), 3),
        "p95": round(float(np.percentile(array, 95)), 3),
        "max": round(float(array.max()), 3),
    }


def summarise(runs: Sequence[RunTiming]) -> dict[str, Any]:
    """Seconds by route, milliseconds by node, and cost and tokens a run."""
    if not runs:
        return {"runs": 0, "seconds": {}, "by_route": {}, "by_node": {}}
    routes: dict[str, list[RunTiming]] = defaultdict(list)
    nodes: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        routes[run.route].append(run)
        for node, ms in run.nodes.items():
            nodes[node].append(ms)
    return {
        "runs": len(runs),
        "seconds": spread([run.seconds for run in runs]),
        "by_route": {
            route: {
                "seconds": spread([run.seconds for run in members]),
                **_spending(members),
            }
            for route, members in sorted(routes.items())
        },
        "by_node": {node: {"ms": spread(values)} for node, values in sorted(nodes.items())},
    }


def _spending(runs: Sequence[RunTiming]) -> dict[str, float | None]:
    costs = [run.cost_usd for run in runs]
    known = [cost for cost in costs if cost is not None]
    return {
        "tokens_mean": round(sum(run.tokens for run in runs) / len(runs), 1),
        "cost_usd_mean": round(sum(known) / len(known), 7) if known else None,
    }


def table(summary: dict[str, Any]) -> str:
    """The summary as two Markdown tables: routes in seconds, nodes in milliseconds."""
    lines = [
        "| Route | Runs | p50 s | p95 s | Max s | Tokens a run | Cost a run |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for route, row in summary["by_route"].items():
        seconds = row["seconds"]
        cost = "unknown" if row["cost_usd_mean"] is None else f"${row['cost_usd_mean']:.4f}"
        lines.append(
            f"| {route} | {seconds['n']} | {seconds['p50']:.1f} | {seconds['p95']:.1f} | "
            f"{seconds['max']:.1f} | {row['tokens_mean']:,.0f} | {cost} |"
        )
    lines += ["", "| Node | Runs | p50 ms | p95 ms | Max ms |", "|---|---:|---:|---:|---:|"]
    for node, row in summary["by_node"].items():
        ms = row["ms"]
        lines.append(
            f"| {node} | {ms['n']} | {ms['p50']:,.0f} | {ms['p95']:,.0f} | {ms['max']:,.0f} |"
        )
    return "\n".join(lines)
