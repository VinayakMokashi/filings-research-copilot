# ADR-0018: Orchestrate the copilot as a LangGraph state graph

- **Status:** Accepted
- **Date:** 2026-10-24
- **Phase:** 5

## Context

Phase 5 joins the parts built so far into one copilot:

- the router ([ADR-0017](0017-routing.md));
- the doc agent ([ADR-0012](0012-query-understanding-and-rewriting.md), [ADR-0013](0013-answer-format.md));
- the data agent ([ADR-0015](0015-reuse-text2sql-analyst.md)), and the hybrid of the two;
- replies for briefs, small talk and declines.

The next steps add a loop (a validator that sends a draft back at most twice, step 5.3), sampling for numeric answers (5.4) and memory across turns (5.5). The phase is done when every node shows up in a trace, and in Phase 6 an API streams the copilot's progress to a browser.

So the orchestration needs:

- branches by route now, and loops next;
- events as each step happens, for traces now and the API later;
- conversation state that outlives the process, in Postgres;
- every component replaceable by a fake, so tests never reach the network.

## Options considered

| Option | For | Against |
|---|---|---|
| Plain Python: one function that calls the parts in turn | No dependency, and the easiest to read | Per-step events, saved conversation state and loops would all be built by hand, and each step's timing would need code of its own |
| **A LangGraph state graph** | Branches and loops are edges; checkpointers in memory and in Postgres; each node's start and result streamed; a typed state | Adds a framework and langchain-core as dependencies, with a vocabulary of their own |
| An agent that calls the specialists as tools (ReAct style) | Flexible; the model plans | Order and routing become the model's choice, which is harder to test and to evaluate, and costs more model calls; the router has already been measured on its own |

## Decision

1. **A LangGraph `StateGraph`** ([guide](../concepts/langgraph-orchestration.md)) with a typed state of plain JSON values. The nodes are functions over the components, which arrive as protocols, so tests pass fakes.
2. **One path for every question:** rewrite, understand, route, one of six specialists, synthesise, validate, respond. The route node branches through a conditional edge. Synthesise gives every specialist's result one shape. Validate passes the draft on until step 5.3, and rewrite passes the question on until step 5.5.
3. **The state across turns.** The checkpointer keeps a conversation's state, so the first node of each turn clears the previous turn's route, result, draft and response; the history only grows.
4. **Events and traces.** The graph streams with `stream_mode=["tasks", "custom"]` and `version="v2"`. Each node's start and result become `start` and `end` events, timed and with any error. Nodes write their own events (the cues, the route and its reason, the answer's outline, model usage) with the stream writer. `TraceWriter` keeps them as JSON lines: the trace until Langfuse in Phase 6.
5. **Checkpointers.** In memory by default, for tests and one-off questions; `PostgresSaver` on the Compose Postgres for conversations (`poe ask --thread NAME --postgres`).
6. **Quotas.** In a batch run, calls are paced and a rate-limited one is retried after a pause; a spent quota stops the run, so an evaluation can resume later. In an interactive run each call is made once: the router falls back to its semantic half, and a specialist's reply says to try again later.
7. **Cost per task.** After each node, the change in the paced clients' token counts becomes a `usage` event, with its cost at list prices; summing them gives a question's cost, for step 5.6.

## Evidence

- 19 tests in `tests/test_graph.py`, with fakes for every component:
  - each of the six routes runs its own path with a start and an end for every node;
  - answers carry their citations and SQL;
  - a second turn starts clean while the history grows;
  - the trace file holds every event;
  - usage events report tokens;
  - quotas are handled both ways.
- An integration test continues a conversation in Postgres from a second `Copilot`.
- **Live runs with `poe ask`,** on a day the strong model's free quota was spent:
  - **A question from the hybrid set** ("How did 3M's capital expenditure change from 2017 to 2018, and what did the company say it was investing in?"). The router's model call was refused, the semantic router routed it to `hybrid`, and the hybrid agent answered from its cached calls with the figures from the query and the reasons from three filing pages, all cited. The trace has a start and an end for each of its 7 nodes. The route node took 12.8 s, almost all of it the gateway retrying the refused call; the other nodes together took under a second.
  - **A two-turn conversation in Postgres:** "Hi! Which companies do you cover?" went to small talk, which listed the 40 companies, and "Should I buy Nike stock right now?" was declined. The second question, asked from a new process, continued the thread as its second turn.
- The end-to-end run on FinanceBench dev is step 5.6's.

## Consequences

- **New dependencies:** `langgraph` 1.2, `langgraph-checkpoint-postgres` and `psycopg[binary]`, with `langchain-core` through LangGraph.
- **State stays JSON.** A doc or hybrid answer keeps its cited sources' text in the state, for the validator, so each turn's checkpoint holds a few thousand tokens of text.
- **The router first.** Every question pays one router call before a specialist starts.
- **Loops are edges.** The validator (step 5.3) and follow-up rewriting (step 5.5) replace their pass-through nodes, without changing the rest of the graph.
- **Phase 6 reuses the stream.** The API streams the same events over SSE, and Langfuse can take the same per-node spans.

## References

- LangGraph documentation: [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [streaming](https://docs.langchain.com/oss/python/langgraph/streaming) and [persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
- Yao et al., [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629), 2022, for the tool-calling alternative.
