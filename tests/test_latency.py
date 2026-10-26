"""Latency and cost from trace events: complete runs only, by route and by node."""

from __future__ import annotations

from typing import Any

import pytest

from copilot.eval.latency import read_runs, spread, summarise, table


def run(
    name: str, route: str, start: str, end: str, nodes: list[tuple[str, float]]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [{"run": name, "ts": start, "type": "start", "node": "rewrite"}]
    for node, ms in nodes:
        events.append({"run": name, "ts": start, "type": "end", "node": node, "ms": ms})
    events.append(
        {
            "run": name,
            "ts": start,
            "type": "event",
            "node": "route",
            "event": "usage",
            "tokens_by_model": {"groq/openai/gpt-oss-120b": [900, 100]},
            "cost_usd": 0.0002,
        }
    )
    events.append({"run": name, "ts": end, "type": "response", "route": route})
    return events


EVENTS = [
    *run("a", "doc", "2026-10-26T05:00:00.000+00:00", "2026-10-26T05:00:12.500+00:00",
         [("route", 500.0), ("doc", 9000.0), ("validate", 1000.0), ("validate", 800.0)]),
    *run("b", "data", "2026-10-26T05:01:00.000+00:00", "2026-10-26T05:01:04.000+00:00",
         [("route", 700.0), ("data", 3000.0)]),
    {"run": "c", "ts": "2026-10-26T05:02:00.000+00:00", "type": "start", "node": "rewrite"},
    {"run": "c", "ts": "2026-10-26T05:02:01.000+00:00", "type": "error", "error": "quota"},
]  # fmt: skip


def test_only_runs_that_reached_their_response_count() -> None:
    runs = read_runs(EVENTS)
    assert [(r.run, r.route, r.seconds) for r in runs] == [("a", "doc", 12.5), ("b", "data", 4.0)]
    assert runs[0].nodes["validate"] == 1800.0  # two checks, added up
    assert (runs[0].tokens, runs[0].cost_usd) == (1000, 0.0002)


def test_a_run_with_an_unpriced_model_has_no_cost() -> None:
    events = run("x", "doc", "2026-10-26T05:00:00+00:00", "2026-10-26T05:00:01+00:00", [])
    events[1]["cost_usd"] = None
    assert read_runs(events)[0].cost_usd is None


def test_spread_reports_median_95th_percentile_and_maximum() -> None:
    assert spread([1.0, 2.0, 3.0, 4.0]) == {"n": 4, "p50": 2.5, "p95": 3.85, "max": 4.0}


def test_summary_by_route_and_node() -> None:
    summary = summarise(read_runs(EVENTS))
    assert summary["runs"] == 2
    assert summary["by_route"]["doc"]["seconds"]["p50"] == 12.5
    assert summary["by_route"]["data"]["cost_usd_mean"] == pytest.approx(0.0002)
    assert summary["by_node"]["route"]["ms"] == {"n": 2, "p50": 600.0, "p95": 690.0, "max": 700.0}
    rendered = table(summary)
    assert "| doc | 1 | 12.5 | 12.5 | 12.5 | 1,000 | $0.0002 |" in rendered
    assert "| validate | 1 | 1,800 | 1,800 | 1,800 |" in rendered


def test_no_complete_runs_summarise_to_nothing() -> None:
    assert summarise([]) == {"runs": 0, "seconds": {}, "by_route": {}, "by_node": {}}
