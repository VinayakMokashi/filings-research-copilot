"""Running the copilot's graph with streamed events and traces (step 5.1).

A run's trace is the graph's own event stream. `Copilot.stream` turns LangGraph's stream
into events:

- `start` and `end` for every node, with the milliseconds between them and any error;
- `event`: each custom event a node emitted, such as the cues, the route, the answer and
  the model tokens it used;
- `error`, if the run stopped on an exception, which is raised again after it, or because
  the caller stopped reading;
- `response`, the reply, last.

`Copilot.details` reads what the latest turn's state holds beyond its response, such as the
sources an answer was written from and its draft before the validator's first check, for
the API's record of an exchange (step 9.2).

Every event carries the time, the run's id, the conversation's id (the thread) and the
turn. Each goes to the run's sink: a `TraceWriter` appends it to a file, one JSON object a
line; `copilot.agents.tracing` sends it to Langfuse; a `Fanout` does both.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Generator, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StateSnapshot, StreamMode

from copilot.agents.graph import Components, CopilotState, Turn, build_graph
from copilot.agents.router import Route

STREAM_MODES: list[StreamMode] = ["tasks", "custom"]


class Sink(Protocol):
    """Where a run's events go, one at a time."""

    def write(self, event: dict[str, Any]) -> None: ...


class Fanout:
    """Every event to each of several sinks."""

    def __init__(self, *sinks: Sink | None) -> None:
        self.sinks = [sink for sink in sinks if sink is not None]

    def write(self, event: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.write(event)


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
        trace: Sink | None = None,
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

    def details(self, thread_id: str) -> dict[str, Any]:
        """What the latest turn's state holds beyond its response: the specialist's result
        with every source's text, the validator's verdict and revisions, the router's
        decision, and the result as it stood before its first check when it was revised."""
        config = _config(thread_id)
        values = self.graph.get_state(config).values
        revisions = int(values.get("revisions", 0))
        draft = first_draft(self.graph.get_state_history(config)) if revisions else None
        return {
            "result": values.get("result", {}),
            "validation": values.get("validation", {}),
            "revisions": revisions,
            "decision": values.get("decision", {}),
            "draft": draft,
        }

    def stream(
        self,
        question: str,
        *,
        thread_id: str,
        user_id: str = "default",
        route: Route | None = None,
        avoid_arm: str | None = None,
    ) -> Generator[dict[str, Any]]:
        """The run's events as they happen; the last one is the response.

        `route` takes that route without asking the router, as a request for a brief does;
        `avoid_arm` keeps the doc agent from answering with that arm, as a second answer to
        the same question does.
        """
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

        # Set on every turn, so what was asked for once doesn't carry over to the next turn.
        inputs: CopilotState = {
            "question": question,
            "requested_route": route or "",
            "avoid_arm": avoid_arm or "",
        }
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
        except GeneratorExit:  # the caller stopped reading, as a client that hangs up does
            event("error", error="Stopped: the caller stopped reading.")
            raise
        except Exception as exc:
            yield event("error", error=f"{type(exc).__name__}: {exc}"[:500])
            raise
        response = self.graph.get_state(config).values.get("response", {})
        yield event("response", **response)

    def ask(
        self,
        question: str,
        *,
        thread_id: str,
        user_id: str = "default",
        route: Route | None = None,
        avoid_arm: str | None = None,
    ) -> dict[str, Any]:
        """The response to one question, once the whole run is done."""
        response: dict[str, Any] = {}
        events = self.stream(
            question, thread_id=thread_id, user_id=user_id, route=route, avoid_arm=avoid_arm
        )
        for item in events:
            if item["type"] == "response":
                response = item
        return response


def first_draft(history: Iterable[StateSnapshot]) -> dict[str, Any] | None:
    """The latest turn's result as it stood before its first check, from the thread's
    checkpoints, newest first: the oldest one waiting for `validate` since the turn began."""
    found = None
    for snapshot in history:
        if snapshot.next == ("validate",):
            found = snapshot.values.get("result")
        elif snapshot.next == ("rewrite",):
            break  # the turn's first step: anything older belongs to an earlier turn
    return found


def _config(thread_id: str, user_id: str = "default") -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id, "user_id": user_id}}
