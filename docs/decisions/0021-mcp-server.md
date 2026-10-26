# ADR-0021: Serve the copilot over MCP, with lookups in the server and questions through the API

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** 6

## Context

The plan's fifth goal is a copilot other AI applications can use: an MCP server that works from a standard MCP client such as Claude Desktop. A client of this kind brings its own model, which reads tool results and decides what to call next, so the server's job is to give that model good material, not necessarily finished answers.

The copilot's capabilities cost very different amounts:

- **Searching the filings** embeds the query and asks Qdrant: about 50 ms on a laptop CPU, and no model call.
- **Looking up a figure** in the facts database is a read-only SQLite query: milliseconds, no model call.
- **Asking the copilot** runs the agents: several model calls on the free tier, 10 to 60 seconds, and a share of a daily token quota. The API guards that with daily question quotas, an answer cache and one run at a time ([ADR-0020](0020-api-and-streaming.md)).

[ADR-0020](0020-api-and-streaming.md) expected the MCP server to call the copilot in its own process. Building the server showed why it shouldn't.

## Options considered

| Option | For | Against |
|---|---|---|
| Everything in the MCP process | One process; works without the API | A second copilot outside the API's quotas, cache and lock, which any MCP client could use to spend the model quota; each client launch builds the agents |
| Everything through the API | One gate for every request; a light server | The API would need search and lookup endpoints that nothing else uses, and lookups that cost nothing would stop working whenever the API is down |
| **Lookups in the server, questions through the API** | No model quota is spent outside the API's guards; the lookups work on their own; the server starts quickly | Two dependencies: the local data for lookups, the API for questions |

## Decision

1. **Three read-only tools.**
   - `search_filings`: passages from the filings with their citation label and page. It is the doc agent's retrieval without its model-written rewrites: dense search over page chunks ([ADR-0011](0011-retrieval-baseline.md)) inside the filings that a company, fiscal year and form pick out, or that the query itself names ([ADR-0012](0012-query-understanding-and-rewriting.md)).
   - `query_financials`: one company's annual values of one metric from the facts database, each as first reported in that year's 10-K, with the latest filing's figure where it was restated ([ADR-0008](0008-xbrl-normalisation.md)). The tool's description lists the 28 metrics.
   - `ask_copilot`: a question sent to `POST /v1/ask`. The server reads the event stream, turns each step's start into an MCP progress notification ("Choosing who answers", "Checking every cited sentence") and returns the answer, its citations, its SQL and what the sources lacked. Every MCP client counts as one visitor, `mcp-server`, against the daily quota.
2. **Resources:** `filing://{doc_name}/{page}` for a page's text, numbered from 1 as in the citations and limited to the filings in the index; `copilot://filings`, `copilot://companies` and `copilot://metrics` for what the tools can be asked about.
3. **A prompt,** `compare_companies`: figures from `query_financials` side by side, explanations from `search_filings`, every figure and explanation cited, and gaps stated rather than estimated.
4. **Typed results and helpful errors.** Each tool declares an output schema and returns structured content. A request the tools can't serve, such as an unknown metric or a company outside the corpus, comes back as a tool error that says what would work, such as the list of metrics.
5. **Filing text is treated as data.** Instruction-like sentences are replaced before text leaves the server, as they are before it reaches the copilot's own prompts ([prompt injection](../concepts/prompt-injection.md)), because the client's model reads it too.
6. **Two transports:** stdio (`poe mcp`), which desktop clients launch, and streamable HTTP (`--transport streamable-http`, port 8001) for the Compose stack. Logs go to stderr, because stdout carries the protocol on stdio.
7. **A quick start.** The search index, its embedding model and the doc agent's module, which imports LiteLLM, load on the first call rather than at startup, so a client connecting doesn't wait for them.

## Evidence

- **Tests** (`tests/test_mcp.py`, 18): filters and query resolution choose the filings; passages carry their label, page and resource, with an injected instruction removed; unknown companies, metrics and filters explain themselves; the index is built once, and an unreachable index says so; figures with their restatements; pages counted from 1; every tool read-only with an output schema; `ask_copilot` posting to the API, relaying the steps as progress and turning a 429 or an outage into a tool error; resources, templates and the prompt; and the real server started as a process over stdio.
- **Live,** against the local index and database: a search for capital spending in 3M's fiscal 2018 10-K returned the page with the geographic capital spending table, PDF page 39, scored 0.80; "What drove Boeing's revenue change in 2022?" resolved to Boeing's fiscal 2022 10-K on its own; 3M's capital expenditure for fiscal 2016 to 2019 came back as $1,420, $1,373, $1,577 and $1,699 million; and `ask_copilot` answered "What was 3M's capital expenditure in 2018?" through the API in 10.1 s, relaying eight steps as progress, then from the API's cache in under a quarter of a second when asked again.
- **In an MCP host:** asked for 3M's fiscal 2018 capital expenditure and its split by region, the host's model called both lookup tools at once and answered in 23 seconds, citing the facts database for the $1,577 million total and PDF page 39 of the 10-K for the four regions.

## Consequences

- **`ask_copilot` needs the API.** The server finds it at `FRC_API_URL`; the other tools need only Qdrant and the local data.
- **One quota for all MCP clients.** They share the `mcp-server` visitor's daily questions, 20 by default; that is deliberate for a free-tier demo.
- **The server runs from the repository.** A desktop client starts it with `uv run --directory <repo> python -m copilot.mcp`, so `.env` and `data/` resolve there.
- **No public MCP endpoint yet.** The HTTP transport has no authentication, so it stays on localhost and the Compose network; exposing it in Phase 8 would need OAuth, as the MCP specification describes for remote servers.

## References

- Model Context Protocol, [Specification](https://modelcontextprotocol.io/specification), revision 2026-07-28.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), version 2.
- The [MCP server guide](../concepts/mcp-server.md).
