# ADR-0020: Serve the copilot over HTTP with FastAPI, streaming the graph's events as server-sent events

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** 6

## Context

Phase 6 puts the copilot in front of people and other tools: a Streamlit UI, an MCP server, and in Phase 8 public addresses on Cloud Run. An answer takes seconds: the router's model call, the specialist's retrieval and answer, the validator's check and perhaps a revision. A client that waits blind for all of it looks broken.

The graph already reports every step as it happens ([ADR-0018](0018-graph-design.md)): a start and a timed end for each node, the nodes' own events (the route, the outline, model usage) and the response last. The question is how to carry that to a client.

Three constraints shape the answer:

- **One run at a time in a process.** The agents' clients count tokens per client, and each node's usage is the change in those counts while it runs; two runs at once would count each other's tokens. Their disk caches are shared files too.
- **Plain HTTP.** Cloud Run serves HTTP requests and streams responses, and a local Compose stack should need nothing special in between.
- **Testable without models.** The application must take its parts from outside, so tests pass fakes.

## Options considered

| Option | For | Against |
|---|---|---|
| One JSON response when the answer is ready | The simplest client | No progress for the 5 to 30 seconds an answer takes; long requests meet proxy timeouts |
| **Server-sent events on the response to a POST** | A one-way stream from server to client, which is all an answer needs; plain HTTP through any proxy; FastAPI streams them natively from a generator, with a keep-alive comment after 15 seconds of silence | A browser's `EventSource` takes only a URL, so it can't send a question in a POST body; a client reads the stream with an HTTP client instead |
| WebSockets | Two-way, little overhead per message | Nothing travels from client to server mid-answer; long-lived stateful connections complicate proxies and scaling |
| A job id, polled | Works with any client | Job state to store, a second endpoint, and the poll interval's delay |

## Decision

1. **A FastAPI application built by `create_app(services)`.** Given services, it uses them, as tests do; otherwise it builds the real ones once at startup: the copilot, a feedback store, the parsed pages and the readiness checks.
2. **`POST /v1/ask` answers as server-sent events:** `meta` first (the request's id and the conversation's), then the graph's events with the schema of the traces (`start`, `end`, `event`, `error`, `response`), and `done` last. Each event has a sequence number as its id and JSON as its data. A failure mid-run is an `error` event followed by `done`; HTTP errors happen only before the stream starts, such as 422 for an invalid request.
3. **Limits before any run:** a question of at most 2,000 characters, ids of at most 64 letters, digits, hyphens or underscores, and no unknown fields.
4. **One run at a time.** A lock admits one copilot run per process; a request that waits more than two minutes for it gets a busy error instead of a hung connection.
5. **Request ids.** Every response carries `X-Request-ID`: the caller's when valid, a new one otherwise. It is logged with every request and sent in `meta`, so feedback can name the answer it is about.
6. **Health.** `GET /healthz` says the process is up; `GET /readyz` checks the facts database, the parsed pages, Qdrant, the model key and, when used, Postgres, and answers 503 when any check fails, for Compose and Cloud Run probes.
7. **Feedback and sources.** `POST /v1/feedback` keeps a thumbs up or down and a comment, in Postgres or in memory, for Phase 9's preference pairs. `GET /v1/sources/{doc_name}/{page}` returns a cited page with its label and section, for the UI's citation drawer; filing names must match a fixed pattern, so a path can't climb out of the pages folder.
8. **State:** `FRC_API_STATE` keeps conversations, notes and feedback in memory (the default) or in the Compose Postgres.
9. **Briefs wait for Phase 7.** `POST /v1/brief` arrives with the brief crew; until then a request for a brief goes through `/v1/ask`, whose router sends it to the brief note.

## Evidence

- **Tests with fakes** (`tests/test_api.py`, 12): the event order of a streamed answer; a follow-up on its thread with the caller's request id; invalid requests refused before any run; one error event and then `done`, whether the graph fails or fails before it starts; the busy error; feedback kept; a page served with its label, and missing or ill-named pages refused; every endpoint in the OpenAPI document.
- **A live run** against the local stack: `/readyz` passed all four checks, a cited page came back labelled "3M, Form 10-K for fiscal 2018, PDF page 60", and "Hi! Which companies do you cover?" streamed `meta`, a start and an end for each of the eight nodes on its path, the reply listing the companies covered, and `done`. The router's call to gpt-oss-120b took 4.7 s and the small-talk reply came from the cache in 6 ms.

## Consequences

- **Clients read a POST's stream.** The Streamlit UI and the MCP server read it with an HTTP client. This record first had the MCP server call the copilot in its own process; [ADR-0021](0021-mcp-server.md) sends its questions through the API instead.
- **The event schema is an interface.** The API sends the trace's events as they are, so a change to a node's events changes what clients receive; the routes are under `/v1` for that reason.
- **One process answers one question at a time.** That suits a demo on the free tier; Phase 8 scales by running more instances. Metering each run on its own would lift the lock.

## References

- WHATWG, [HTML Living Standard: Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html).
- MDN, [Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).
- FastAPI, [Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/).
- The [SSE streaming guide](../concepts/sse-streaming.md).
