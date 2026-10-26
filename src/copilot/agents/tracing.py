"""Langfuse traces of the copilot's runs (step 6.5).

`LangfuseTracer` reads the same events as the JSON-line trace (`copilot.agents.runner`) and
builds one Langfuse trace a run:

- the run as the root observation, with the question as input, the reply as output, and
  the route, whether it answered and the validator's verdict as metadata; the conversation
  is the trace's session;
- a span for each node, from its start to its end, marked as an error when the node failed;
- a generation under the node for each model it called, with the prompt and completion
  tokens and their cost at the gateway's prices;
- the nodes' other events, such as the route and the cues, as events under their node.

The API advances the event stream from worker threads, so every observation is created
under an explicit parent rather than through the context a `with` block would set.
Langfuse's client sends observations in the background; `close` flushes what is left.
Without both keys, `build_tracer` returns None and nothing is sent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langfuse import Langfuse, propagate_attributes

from copilot.config import Settings
from copilot.llm.gateway import token_cost

ROOT = "ask"
NODE_TYPES = {"doc": "agent", "data": "agent", "hybrid": "agent", "validate": "evaluator"}
PLUMBING = frozenset({"ts", "run", "thread", "turn", "type", "node", "event"})


@dataclass
class _Run:
    root: Any
    nodes: dict[str, Any] = field(default_factory=dict)  # each node's open span


class LangfuseTracer:
    """A Langfuse trace for each run; see the module docstring."""

    def __init__(self, client: Langfuse, tags: tuple[str, ...] = ("api",)) -> None:
        self.client = client
        self.tags = list(tags)
        self._runs: dict[str, _Run] = {}

    def write(self, event: dict[str, Any]) -> None:
        run = self._run(event)
        kind = event.get("type")
        node = str(event.get("node", ""))
        if kind == "start":
            run.nodes[node] = run.root.start_observation(
                name=node, as_type=NODE_TYPES.get(node, "span")
            )
        elif kind == "end":
            span = run.nodes.pop(node, None)
            if span is not None:
                if event.get("error"):
                    span.update(level="ERROR", status_message=str(event["error"])[:500])
                span.end()
        elif kind == "event":
            parent = run.nodes.get(node, run.root)
            if event.get("event") == "usage":
                self._generations(parent, event)
            else:
                parent.create_event(name=str(event.get("event")), metadata=_details(event))
        elif kind == "error":
            run.root.update(level="ERROR", status_message=str(event.get("error"))[:500])
            self._finish(event)
        elif kind == "response":
            run.root.update(
                input=event.get("question"),
                output=event.get("text"),
                metadata={
                    "route": event.get("route"),
                    "answered": event.get("answered"),
                    "validation": event.get("validation"),
                },
            )
            self._finish(event)

    def close(self) -> None:
        """Send whatever is still queued."""
        self.client.flush()

    def _run(self, event: dict[str, Any]) -> _Run:
        key = str(event.get("run"))
        if key not in self._runs:
            with propagate_attributes(
                session_id=str(event.get("thread")), trace_name=ROOT, tags=self.tags
            ):
                root = self.client.start_observation(
                    name=ROOT, as_type="agent", metadata={"turn": event.get("turn")}
                )
            self._runs[key] = _Run(root)
        return self._runs[key]

    def _generations(self, parent: Any, event: dict[str, Any]) -> None:
        for model, (prompt, completion) in dict(event.get("tokens_by_model", {})).items():
            cost = token_cost(model, prompt, completion)
            generation = parent.start_observation(
                name=model,
                as_type="generation",
                model=model,
                usage_details={"input": prompt, "output": completion},
                cost_details={"total": cost} if cost is not None else None,
            )
            generation.end()

    def _finish(self, event: dict[str, Any]) -> None:
        run = self._runs.pop(str(event.get("run")))
        for span in run.nodes.values():  # nodes a failure left open
            span.end()
        run.root.end()


def _details(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key not in PLUMBING}


def build_tracer(settings: Settings) -> LangfuseTracer | None:
    """The tracer for Langfuse, or None when its keys aren't set."""
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        environment=settings.env,
    )
    return LangfuseTracer(client)
