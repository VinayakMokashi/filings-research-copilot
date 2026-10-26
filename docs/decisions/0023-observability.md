# ADR-0023: Trace each run in Langfuse from the graph's own events

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** 6

## Context

Every answer passes through up to nine nodes and several model calls on three models. To see why an answer was slow, wrong or expensive, each step's time, tokens and cost has to be on record and easy to browse. The plan's last Phase 6 step asks for traces with a span per node, with tokens and cost, and for latency metrics.

The graph already reports what Langfuse would need ([ADR-0018](0018-graph-design.md)): the runner turns LangGraph's stream into events (a start and a timed end for each node, the nodes' own events, among them a `usage` event with the tokens by model, and the response last), and the API writes them to a JSON-lines file. Two facts constrain how traces are built:

- **Worker threads.** The API reads the run's events from a synchronous generator that FastAPI advances in its thread pool, so consecutive events can arrive on different threads. Tracing that relies on the current context (a `with` block, or a decorator) loses track of the parent span between events.
- **The free tier.** Langfuse's free plan includes 50,000 units a month, each trace, observation or score counting one; a question makes about twenty.

## Options considered

| Option | For | Against |
|---|---|---|
| LangChain's Langfuse callback handler on the graph | One line of setup; spans for every LangGraph step | The model calls go through the project's gateway, not LangChain models, so tokens and cost would be missing; spans follow LangGraph's internals rather than the nodes' own events |
| LiteLLM's Langfuse callback | Every model call traced with tokens and cost | Calls not tied to the node that made them; nothing about the nodes, routes or verdicts |
| **A sink that turns the runner's events into observations** | The trace mirrors the JSON-lines file exactly; tokens and cost come from the node that spent them; parents are explicit, so threads don't matter | The project maps events to observations itself |
| Self-hosted Langfuse in Compose | No third party sees questions | Six more containers (Postgres, ClickHouse, Redis, object storage and two Langfuse services) on a laptop already short of memory |

## Decision

1. **A `LangfuseTracer` sink** (`copilot.agents.tracing`), fed by the runner like the JSON-lines writer, through a `Fanout` to both. Each run becomes one trace:
   - the run is the root observation, typed as an agent, with the question as input, the reply as output, and the route, whether it answered and the validator's verdict as metadata; the conversation is the trace's session;
   - each node is a span from its start to its end, typed as an agent for the three specialists and as an evaluator for the validator, and marked as an error when it failed;
   - each model a node called is a generation under it, with the prompt and completion tokens and their cost at the gateway's prices;
   - the nodes' other events (the cues, the route, the verdict) are events under their node.
2. **Explicit parents.** Every observation is created from its parent object, never from the ambient context.
3. **Every trace closes.** A run that fails ends its open spans and its root as errors; a run whose caller stops reading, as a client that hangs up does, is now traced as stopped by the runner itself.
4. **Off unless configured.** Tracing starts only when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set; `LANGFUSE_BASE_URL` picks the region. The API flushes the client when it shuts down. Only the API traces: batch evaluations keep their JSON-lines files, which would use up the free plan's units.
5. **Latency from the same events.** `copilot.eval.latency` and `poe latency-report` give the median, 95th percentile and slowest run by route and by node, with tokens and cost a run, from any trace file, offline.

## Evidence

- **Tests** (`tests/test_tracing.py`) drive the real Langfuse SDK into an in-memory OpenTelemetry exporter, so they need no account: one trace a run with its session, input and output; a span per node under the root; a generation per model with its tokens and the gateway's cost; events under their node; failed nodes and runs marked as errors, with every span closed. The runner's test checks that a run whose caller stops reading is traced as stopped; the latency module has its own tests.
- **Live,** against a Langfuse Cloud project: three questions through the API (a figures question, small talk and a hybrid question) arrived as three traces of 17 to 20 observations, each with its node spans, the validator as an evaluator, and a generation for every model call with its usage and cost. The hybrid question's four model calls on three models came to $0.0027.

## Consequences

- **Questions and answers leave the machine** when tracing is on: they are stored in Langfuse Cloud's chosen region. The public demo will need to say so.
- **The event schema now feeds two sinks.** A new node or event appears in Langfuse without changes to the tracer; a renamed field would need one.
- **The free plan fits the demo.** At about twenty units a question, 50,000 a month allows some 2,500 traced questions, against a quota of 200 a day.

## References

- Langfuse, [Get started with tracing](https://langfuse.com/docs/observability/get-started), [data regions](https://langfuse.com/security/data-regions) and [pricing](https://langfuse.com/pricing).
- OpenTelemetry, [Traces](https://opentelemetry.io/docs/concepts/signals/traces/).
- The [observability guide](../concepts/observability.md).
