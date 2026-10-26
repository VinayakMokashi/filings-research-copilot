"""Running the copilot's graph with streamed events and JSON-line traces (step 5.1).

Until Langfuse arrives (Phase 6), a run's trace is the graph's own event stream, kept as
JSON lines. `Copilot.stream` turns LangGraph's stream into events:

- `start` and `end` for every node, with the milliseconds between them and any error;
- `event`: each custom event a node emitted, such as the cues, the route, the answer and
  the model tokens it used;
- `error`, if the run stopped on an exception, which is raised again after it;
- `response`, the reply, last.

Every event carries the time, the run's id, the conversation's id (the thread) and the
turn. A `TraceWriter` appends them to a file, one JSON object a line.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StreamMode

from copilot.agents.graph import Components, CopilotState, Turn, build_graph

STREAM_MODES: list[StreamMode] = ["tasks", "custom"]


class TraceWriter:
    """Appends events to a JSON Lines file, creating its folder on the first event."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


class Copilot:
    """The graph and its checkpointer, one question at a time; see the module docstring.

    The checkpointer keeps each conversation's state between questions: in memory unless
    another is given, such as `PostgresSaver` for conversations that outlive the process.
    """

    def __init__(
        self,
        parts: Components,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        trace: TraceWriter | None = None,
    ) -> None:
        self.checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
        self.graph = build_graph(parts, self.checkpointer)
        self.trace = trace

    def history(self, thread_id: str) -> list[dict[str, Any]]:
        """The conversation's finished turns, oldest first."""
        values = self.graph.get_state(_config(thread_id)).values
        return list(values.get("history", []))

    def record(self, thread_id: str, turn: Turn) -> None:
        """Add a finished exchange to a conversation without running the graph, as an answer
        served from a cache is, so that a follow-up on the thread can build on it."""
        self.graph.update_state(_config(thread_id), {"history": [turn]}, as_node="remember")

    def stream(
        self, question: str, *, thread_id: str, user_id: str = "default"
    ) -> Iterator[dict[str, Any]]:
        """The run's events as they happen; the last one is the response."""
        config = _config(thread_id, user_id)
        base = {
            "run": uuid.uuid4().hex[:12],
            "thread": thread_id,
            "turn": len(self.history(thread_id)) + 1,
        }
        started: dict[str, float] = {}

        def event(kind: str, /, **data: Any) -> dict[str, Any]:
            record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), **base}
            record |= {"type": kind, **data}
            if self.trace is not None:
                self.trace.write(record)
            return record

        inputs: CopilotState = {"question": question}
        parts = self.graph.stream(inputs, config, stream_mode=STREAM_MODES, version="v2")
        try:
            for part in parts:
                if part["type"] == "custom":
                    yield event("event", **part["data"])
                elif part["type"] == "tasks":
                    task = part["data"]
                    if "input" in task:  # a node starting
                        started[task["id"]] = time.perf_counter()
                        yield event("start", node=task["name"])
                    else:  # a node's result or error
                        began = started.pop(task["id"], time.perf_counter())
                        elapsed = round((time.perf_counter() - began) * 1000, 1)
                        yield event("end", node=task["name"], ms=elapsed, error=task.get("error"))
        except Exception as exc:
            yield event("error", error=f"{type(exc).__name__}: {exc}"[:500])
            raise
        response = self.graph.get_state(config).values.get("response", {})
        yield event("response", **response)

    def ask(self, question: str, *, thread_id: str, user_id: str = "default") -> dict[str, Any]:
        """The response to one question, once the whole run is done."""
        response: dict[str, Any] = {}
        for item in self.stream(question, thread_id=thread_id, user_id=user_id):
            if item["type"] == "response":
                response = item
        return response


def _config(thread_id: str, user_id: str = "default") -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id, "user_id": user_id}}
