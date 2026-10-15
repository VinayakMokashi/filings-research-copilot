# Build log

A dated journal of every working session, newest first. Each entry uses this template:

```markdown
### YYYY-MM-DD · Phase N · Short title
- **Goal:**
- **Done:**
- **Commands:**
- **Results:**
- **Problems and fixes:**
- **Decisions:** (links to ADRs)
- **Next:**
```

---

### 2026-10-15 · Phase 0 · Foundations

- **Goal:** a repository where every later phase lands cleanly.
- **Done:**
  - Scaffolded the package with uv (hatchling build, `src/copilot` layout, Python 3.12) and committed `uv.lock`. Runtime dependencies: LiteLLM 1.105.1, pydantic-settings 2.16.0, structlog 26.1.0, httpx 0.28.1. Dev: ruff 0.17.0, mypy 2.4.0, pytest 9.1.1, poethepoet 0.48.0, pre-commit 4.7.0.
  - Typed settings (`copilot.config`) and structured logging (`copilot.logs`).
  - LLM gateway v0 on LiteLLM's router: model roles, retries, fallbacks, token and cost accounting, reasoning handling, key redaction, and `FakeLLM` for tests ([ADR-0005](decisions/0005-llm-gateway.md)).
  - Docker Compose with Qdrant 1.19.2 and Postgres 18.6, bound to 127.0.0.1, with health checks.
  - CI with lint, format, strict types, tests, and a checksum-verified gitleaks scan of the full history (`.gitleaks.toml` adds explicit rules for this project's key formats). Dependabot handles weekly updates, and a GitHub Pages workflow deploys the project page. Every action is pinned to a commit SHA ([ADR-0004](decisions/0004-tooling-and-workflow.md)).
  - Decided that AWS runs in demo windows ([ADR-0003](decisions/0003-aws-demo-windows.md)).
  - Wrote the concept guide [llm-gateway.md](concepts/llm-gateway.md) and the runbooks [local-setup.md](runbooks/local-setup.md) and [publishing-the-project-page.md](runbooks/publishing-the-project-page.md).
  - Ran a full pre-push review across code, tooling, security, documentation accuracy and presentation. Each finding was checked independently before being accepted: 40 were confirmed and fixed, and 13 were rejected.
  - Created the public GitHub repository, set Pages to deploy from GitHub Actions, and pushed the history as 10 commits.
- **Commands:** `uv run poe check`, `uv run poe services-up`, `uv run poe services-down`, `docker compose config`, gitleaks rule probes in Docker, `uv run poe secrets`, `gh repo create`, `gh api -X POST repos/OWNER/REPO/pages -f build_type=workflow`.
- **Results:** ruff clean; mypy strict reports no issues in 16 files; 39 tests pass offline. Qdrant `/readyz` returns 200 and Postgres 18.6 reports healthy on 127.0.0.1. gitleaks finds no leaks in the 10 commits. On GitHub, the first push passed CI (checks and the secret scan) and deployed the [project page](https://vinayakmokashi.github.io/filings-research-copilot/).
- **Problems and fixes:**
  - **Port conflict.** A native PostgreSQL 17 Windows service already listened on 5432, and Docker bound the same port, so `localhost:5432` could reach either server. The container now publishes on 5433 (override with `POSTGRES_PORT`).
  - **Services exposed on the network.** Both services were published on all network interfaces, so anyone on the same network could reach an unauthenticated vector store and a database with a known password. They now bind to 127.0.0.1. The URL defaults use 127.0.0.1 because `localhost` resolves to `::1` first on Windows.
  - **Health checks.** The Qdrant image has no curl or wget, so its health check sends the `/readyz` request through a bash `/dev/tcp` socket. The Postgres check now probes over TCP: on first start, the image's init server listens only on the Unix socket.
  - **Every call looked like a fallback.** Live providers report their own model id without LiteLLM's prefix, so every live call would have looked like a fallback. The gateway now uses the router's record of the deployment and model group.
  - **Smaller gateway bugs.**
    - Groq's gpt-oss reasoning arrives in a `reasoning` field, and the gateway now keeps it.
    - Models missing from LiteLLM's price map showed a $0 cost and now show none.
    - An empty reply raised `IndexError` and now raises `LLMError`.
    - The router's cooldown hid the real error for 5 seconds, so cooldowns are disabled.
    - Configured API keys are scrubbed from error messages.
  - **Test isolation.** Unit tests now refuse network access. LiteLLM's import-time `.env` loading is switched off with `LITELLM_MODE`, and its model price map is read from the installed package instead of being downloaded at import.
  - **Secret-scan blind spots.** The gitleaks GitHub Action scans only the pushed commit range, which fails when that range starts at the root commit. CI now runs a pinned gitleaks CLI over the full history. gitleaks' default rules caught this project's provider keys only through their generic rule, so `.gitleaks.toml` adds explicit patterns.
  - **Line endings.** Python's `write_text` writes CRLF on Windows, so three files edited by scripts had CRLF endings. `.gitattributes` normalises text to LF in git, and the working copies were converted too. Git Bash's grep strips CR before matching, so line-ending checks read raw bytes instead.
  - **mypy imports.** mypy rejected `from litellm import Router` because LiteLLM doesn't re-export it. Imports now come from `litellm.router` and `litellm.exceptions`.
- **Decisions:** [ADR-0003](decisions/0003-aws-demo-windows.md), [ADR-0004](decisions/0004-tooling-and-workflow.md), [ADR-0005](decisions/0005-llm-gateway.md).
- **Next:** step 0.8 once the Groq key is in `.env` (`uv run poe models`, then `uv run poe smoke`), then Phase 1.

### 2026-10-15 · Planning · Build plan and documentation structure

- **Goal:** turn the chosen idea into an executable plan and set up documentation before writing code.
- **Done:** wrote [PLAN.md](PLAN.md) with 11 phases, each with steps and exit criteria; set up the documentation system ([ADR-0002](decisions/0002-documentation-system.md)); recorded the project choice ([ADR-0001](decisions/0001-choose-filings-research-copilot.md)); started the [concept-guide index](concepts/README.md), the [glossary](glossary.md) and the [project page](site/index.html).
- **Next:** Phase 0.

### 2026-10-12 · Discovery · Project options

- **Goal:** pick a product to build end to end and deploy.
- **Done:** compared three directions: A, an analyst copilot over SEC filings; B, a code-review agent as a GitHub App; C, an adaptive study tutor.
- **Decisions:** chose A ([ADR-0001](decisions/0001-choose-filings-research-copilot.md)).
