# Local setup

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Docker (Docker Desktop on Windows and macOS)
- Git

## 1. Install

```bash
uv sync                       # creates .venv and installs everything from uv.lock
uv run pre-commit install     # run the lint hooks on every commit
```

## 2. Configure

```bash
cp .env.example .env
```

Fill in at least `GROQ_API_KEY`. Empty values count as unset. `.env` is git-ignored.

## 3. Start the local services

```bash
uv run poe services-up        # Qdrant on 127.0.0.1:6333, Postgres on 127.0.0.1:5433; waits until healthy
```

Both services listen on 127.0.0.1 only. Postgres is published on **5433** because a local PostgreSQL install often holds 5432. Change either port with `QDRANT_PORT` or `POSTGRES_PORT` in `.env`, and update `FRC_QDRANT_URL` or `FRC_DATABASE_URL` to match.

Nothing reads from either service yet. Qdrant will hold the filing chunks (Phase 2). Postgres will hold app state: LangGraph checkpoints (Phase 5) and feedback (Phase 6). From Phase 8 it is also where the facts tables are tested before they move to Cloud SQL. Until then the facts stay in SQLite (see PLAN §6).

## 4. Run the checks

```bash
uv run poe check              # ruff, format check, mypy, pytest: the same steps as CI
uv run poe secrets            # gitleaks over the full git history, as CI does (needs Docker)
```

## 5. Live checks (need `GROQ_API_KEY`)

```bash
uv run poe models             # models the key can use, and whether the configured roles are among them
uv run poe smoke              # one call per role through the gateway
```

## 6. Ask the copilot (needs `GROQ_API_KEY`, Qdrant and the facts database)

```bash
uv run poe ask "What was 3M's capital expenditure in 2018?" --verbose   # each step as it runs
uv run poe ask "Hi! Which companies do you cover?" --thread demo --postgres   # a conversation kept in Postgres
```

Each node's start and end is printed as the graph streams it, and every event is appended to `data/traces/<thread>.jsonl`. A later `poe ask "..." --thread demo --postgres` continues the same conversation.

## 7. Serve the API (needs `GROQ_API_KEY`, Qdrant and the facts database)

```bash
uv run poe api                                  # http://127.0.0.1:8000, interactive docs at /docs
curl http://127.0.0.1:8000/readyz               # 200 when every check passes, 503 otherwise
curl -N -X POST http://127.0.0.1:8000/v1/ask -H "Content-Type: application/json" -d '{"question": "What was 3M'"'"'s capital expenditure in 2018?"}'
```

The answer streams as server-sent events: `meta`, then a `start` and an `end` for each node, the nodes' events and the `response`, then `done`. Send the `thread_id` from `meta` with the next question to ask a follow-up. Conversations, notes and feedback live in memory; `FRC_API_STATE=postgres` keeps them in the Compose Postgres. One question is answered at a time; events are also appended to `data/traces/api.jsonl`. Each question counts against daily quotas, 20 per visitor and 200 in total by default (`FRC_API_DAILY_QUESTIONS`, `FRC_API_DAILY_TOTAL`); a client sends `X-Visitor-ID` to be counted as one visitor, or is counted by its address, and a question over either quota gets a 429 with `Retry-After`. Without a `user_id` a caller is anonymous and nothing is noted about them. A question repeated word for word (case, spacing and quote marks aside) in a new anonymous conversation is answered from the cache, with no run and no quota, for seven days (`FRC_API_CACHE_DAYS`; 0 turns it off).

## 8. Use the web UI

```bash
uv run poe api      # first, in one terminal
uv run poe ui       # then, in another: http://127.0.0.1:8501
```

**Ask** streams each question through the API and names the step under way; the answer then shows its sources (switch one on to read the cited page), a chart and table when it came from the facts database, the steps with their times, and thumbs up or down. **Results** lists the evaluations' headline numbers. `FRC_API_URL` points the UI at another API. Streamlit is in the `ui` dependency group, which `uv sync` installs by default.

## 9. Use the MCP server (needs Qdrant and the facts database; `ask_copilot` also needs the API)

```bash
uv run poe mcp                                 # on stdio: it waits for a client; Ctrl+C stops it
uv run poe mcp --transport streamable-http     # or over HTTP, at http://127.0.0.1:8001/mcp
```

A desktop client starts the server itself. For Claude Desktop, add it to `claude_desktop_config.json` (Settings, then Developer, then Edit Config; the file is `%APPDATA%\Claude\claude_desktop_config.json` on Windows and `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS), with the repository's absolute path, written with forward slashes on Windows too:

```json
{
  "mcpServers": {
    "filings-research-copilot": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/filings-research-copilot", "python", "-m", "copilot.mcp"],
      "env": {"FRC_API_URL": "http://127.0.0.1:8000"}
    }
  }
}
```

Restart the client and the server's three tools appear: `search_filings` and `query_financials` work straight away, and `ask_copilot` once `uv run poe api` is serving. `--directory` makes `.env` and `data/` resolve in the repository; the `env` entry is needed only when the API is elsewhere. If the client can't find `uv`, give its full path (`where uv` on Windows, `which uv` elsewhere). Questions through `ask_copilot` count as one visitor against the API's daily quota.

## 10. Run the whole stack in Docker (needs the data built and `GROQ_API_KEY`)

```bash
uv run poe stack-up       # builds the images, starts everything and waits until it is healthy
uv run poe stack-down     # stops and removes the containers; data volumes are kept
```

The API is then on http://127.0.0.1:8000 (docs at /docs), the web UI on http://127.0.0.1:8501 and the MCP server at http://127.0.0.1:8001/mcp. Set `API_PORT`, `UI_PORT` or `MCP_PORT`, in `.env` or the shell, when a port is taken. The containers use `data/` from the repository and the index in the Qdrant volume, so build the facts database ([fetching SEC data](fetching-sec-data.md)) and the parsed pages and index ([ingesting filings](ingesting-filings.md)) first. The API and MCP containers read `.env`; the API keeps its state in the Compose Postgres. `poe services-up` still starts only Qdrant and Postgres. On Linux, if your user id isn't 1000, build with `docker compose --profile app build --build-arg UID=$(id -u)` so the containers can write to `data/cache` and `data/traces`. Logs: `docker compose --profile app logs -f api`.

## Stop the services

```bash
uv run poe services-down      # stops containers; data volumes are kept
docker compose down -v        # also deletes the data volumes
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `VIRTUAL_ENV ... does not match the project environment` warning | Another virtualenv is active in the shell. uv uses the project's `.venv` anyway; run `deactivate` to silence it. |
| `poe services-up` times out | Check that Docker is running, then `docker compose logs qdrant postgres`. |
| `port is already allocated` | Set `QDRANT_PORT` or `POSTGRES_PORT` in `.env` and update the matching URL. |
| `poe smoke` says the key is missing | Add `GROQ_API_KEY` to `.env`, without quotes. |
| `poe models` shows a role as `NOT AVAILABLE` | Set `FRC_LLM_STRONG_MODEL` or `FRC_LLM_FAST_MODEL` to one of the listed models, keeping the `groq/` prefix. |
| CI fails at `uv sync --locked` but `poe check` passes locally | `uv.lock` is out of date. Run `uv lock`, commit it, and use `uv run --locked poe check` to catch this before pushing. |
| `ask_copilot` says the copilot can't be reached, or answers with an HTTP error | Start `uv run poe api`, or set `FRC_API_URL` in `.env` or the client's `env` block when the API listens elsewhere: another program may hold port 8000. |
| `poe stack-up` reports an unhealthy `api` | Read `docker compose --profile app logs api`. `/readyz` must pass: the facts database, the pages, the model key, Qdrant and Postgres. |
| The MCP server doesn't appear in the client | Read the client's log (on Windows, Claude Desktop keeps `mcp.log` and `mcp-server-filings-research-copilot.log` in `%APPDATA%\Claude\logs`), then run the configured command by hand: it should wait silently for input. Anything it prints to stdout breaks the protocol. |
