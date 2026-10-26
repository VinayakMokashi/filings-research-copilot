"""Langfuse traces from the runner's events: the run, its nodes, their models and events.

The real Langfuse client builds the spans, which go to an in-memory exporter instead of
Langfuse's servers.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from langfuse import Langfuse
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from copilot.agents.runner import Fanout
from copilot.agents.tracing import LangfuseTracer, build_tracer
from copilot.config import Settings
from copilot.llm.gateway import token_cost

STRONG = "groq/openai/gpt-oss-120b"
FAST = "groq/qwen/qwen3.8-27b"
BASE = {"run": "r1", "thread": "t1", "turn": 1}
RUN: list[dict[str, Any]] = [
    {"type": "start", "node": "route"},
    {"type": "event", "node": "route", "event": "route", "route": "hybrid", "router": "llm"},
    {"type": "event", "node": "route", "event": "usage", "tokens_by_model": {STRONG: [869, 112]}},
    {"type": "end", "node": "route", "ms": 512.3, "error": None},
    {"type": "start", "node": "hybrid"},
    {
        "type": "event",
        "node": "hybrid",
        "event": "usage",
        "tokens_by_model": {STRONG: [3000, 400], FAST: [1200, 300]},
    },
    {"type": "end", "node": "hybrid", "ms": 9000.0, "error": None},
    {
        "type": "response",
        "question": "How did 3M's capex change?",
        "text": "It rose [1].",
        "route": "hybrid",
        "answered": True,
        "validation": {"checked": True, "faithful": True},
    },
]


def tracer() -> tuple[LangfuseTracer, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key=f"pk-lf-{uuid.uuid4().hex}",  # one client per test; Langfuse keys clients by it
        secret_key="sk-lf-test",
        base_url="http://127.0.0.1:9",
        span_exporter=exporter,
        environment="test",
    )
    return LangfuseTracer(client), exporter


def traced(events: list[dict[str, Any]]) -> list[ReadableSpan]:
    sink, exporter = tracer()
    for event in events:
        sink.write(BASE | event)
    sink.close()
    return list(exporter.get_finished_spans())


def attribute(span: ReadableSpan, name: str) -> Any:
    return (span.attributes or {}).get(name)


def parent_of(span: ReadableSpan, spans: list[ReadableSpan]) -> str | None:
    if span.parent is None:
        return None
    return next(s.name for s in spans if s.context.span_id == span.parent.span_id)


def test_a_run_becomes_one_trace_with_a_span_per_node() -> None:
    spans = traced(RUN)
    root = next(span for span in spans if span.parent is None)
    assert root.name == "ask"
    assert attribute(root, "session.id") == "t1"
    assert attribute(root, "langfuse.trace.name") == "ask"
    assert attribute(root, "langfuse.observation.input") == "How did 3M's capex change?"
    assert attribute(root, "langfuse.observation.output") == "It rose [1]."
    assert attribute(root, "langfuse.observation.metadata.route") == '"hybrid"'
    assert len({span.context.trace_id for span in spans}) == 1
    nodes = {span.name: span for span in spans if parent_of(span, spans) == "ask"}
    assert set(nodes) == {"route", "hybrid"}
    assert attribute(nodes["hybrid"], "langfuse.observation.type") == "agent"


def test_each_model_a_node_called_is_a_generation_with_tokens_and_cost() -> None:
    spans = traced(RUN)
    generations = [
        span
        for span in spans
        if attribute(span, "langfuse.observation.type") == "generation"
        and parent_of(span, spans) == "hybrid"
    ]
    by_model = {attribute(span, "langfuse.observation.model.name"): span for span in generations}
    assert set(by_model) == {STRONG, FAST}
    fast = by_model[FAST]
    assert json.loads(attribute(fast, "langfuse.observation.usage_details")) == {
        "input": 1200,
        "output": 300,
    }
    cost = json.loads(attribute(fast, "langfuse.observation.cost_details"))["total"]
    assert cost == token_cost(FAST, 1200, 300)


def test_other_node_events_become_events_under_their_node() -> None:
    spans = traced(RUN)
    route = next(
        span
        for span in spans
        if span.name == "route" and attribute(span, "langfuse.observation.type") == "event"
    )
    assert parent_of(route, spans) == "route"
    assert attribute(route, "langfuse.observation.metadata.route") == '"hybrid"'


def test_failures_are_marked_and_close_the_trace() -> None:
    failed_node: list[dict[str, Any]] = [
        {"type": "start", "node": "data"},
        {"type": "end", "node": "data", "ms": 3.0, "error": "LLMError: rate limited"},
        {"type": "start", "node": "respond"},
        {"type": "error", "error": "LLMError: rate limited"},
    ]
    spans = traced(failed_node)
    by_name = {span.name: span for span in spans}
    assert set(by_name) == {"ask", "data", "respond"}  # every span ended, the open one too
    assert attribute(by_name["data"], "langfuse.observation.level") == "ERROR"
    assert attribute(by_name["ask"], "langfuse.observation.level") == "ERROR"
    assert "rate limited" in attribute(by_name["ask"], "langfuse.observation.status_message")


def test_a_fanout_sends_every_event_to_each_sink() -> None:
    class Collect:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        def write(self, event: dict[str, Any]) -> None:
            self.events.append(event)

    first, second = Collect(), Collect()
    fanout = Fanout(first, None, second)
    fanout.write({"type": "start"})
    assert first.events == second.events == [{"type": "start"}]


def test_tracing_is_off_without_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    assert build_tracer(Settings(_env_file=None)) is None
    assert build_tracer(Settings(_env_file=None, langfuse_public_key="pk-lf-x")) is None
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", f"pk-lf-{uuid.uuid4().hex}")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-x")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:9")  # the SDK's older name
    both = Settings(_env_file=None)
    assert both.langfuse_base_url == "http://127.0.0.1:9"
    assert build_tracer(both) is not None
