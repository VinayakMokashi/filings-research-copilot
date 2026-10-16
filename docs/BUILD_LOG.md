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

### 2026-10-17 · Phase 1 · Routing eval set

- **Goal:** labelled questions for the router that sends each question to a specialist (step 1.8).
- **Done:**
  - Wrote 66 seed questions across six routes (`doc`, `data`, `hybrid`, `brief`, `smalltalk`, `decline`), with labelling rules for the close calls.
  - `poe paraphrase-routing-seeds` asked `gpt-oss-120b` for three rewrites per seed through the gateway. Every rewrite was reviewed and given a verdict with a reason, kept in `eval/routing/candidates.jsonl`.
  - `copilot.eval.routing`: building the set, a split grouped by seed, the held-out guard and checksums, scoring, and keyword and majority baselines; `poe build-routing-set` and `poe eval-routing`.
  - Wrote the [routing-set data card](data/routing-set.md).
- **Commands:** `uv run poe paraphrase-routing-seeds`, `uv run poe build-routing-set`, `uv run poe eval-routing --baseline keyword`, `uv run poe eval-routing --baseline majority`, `uv run poe check`.
- **Results:**
  - 201 model rewrites: 124 accepted, 37 valid but surplus, and 40 rejected for a source hint (11), added scope (5), a shifted route (2), being too close to another question (7), a refusal (3) or a poem (12). Eight rewrites were written by hand.
  - 198 questions: dev 138 and test 60, with a seed and its paraphrases always on the same side.
  - Keyword baseline on dev: accuracy 0.623 (95% interval 0.543 to 0.703); majority class: 0.217 (0.152 to 0.290).
  - 122 tests pass offline, 18 of them new.
- **Problems and fixes:**
  - **Refusals.** The model refused to paraphrase three `decline` seeds (retirement savings in one stock, revealing the system prompt, hacking a website) and wrote the poem a fourth seed asked for. Those seeds got hand-written rewrites, recorded as such.
  - **A brittle baseline.** The keyword rules score 0.957 on dev seeds but 0.457 on dev paraphrases: they were written while reading the seeds. Testing on seeds alone would have hidden this, which is the reason for the paraphrases.
  - **Invisible typography.** The model writes non-breaking hyphens (U+2011) in "10-K", which keyword rules and tokenisers treat differently from a plain hyphen. The build step normalises them.
  - **Escapes in source files.** `\u2011` in a hand-edited Python string came out as the literal character, which ruff flags as ambiguous (RUF001). The escapes are now written explicitly.
- **Decisions:** none new; the split rule and review rules are in the data card.
- **Next:** the SEC steps (1.3 to 1.6) once the SEC contact is in `.env`, then the SQL eval set (1.7).

### 2026-10-17 · Phase 1 · Evaluation harness

- **Goal:** a harness that turns predictions into scores with honest uncertainty, and a rule for when a change counts as better (step 1.9).
- **Done:**
  - `copilot.eval.metrics`: recall@k, hit@k and reciprocal rank over de-duplicated rankings.
  - `copilot.eval.stats`: percentile bootstrap intervals, a paired permutation test with a bootstrap interval for the difference, McNemar's exact test and Holm–Bonferroni adjustment, all seeded ([ADR-0007](decisions/0007-evaluation-statistics.md)).
  - `copilot.eval.report`: run directories with per-question rows, a JSON summary and a Markdown summary, intervals by question type, and paired comparisons matched by question id.
  - `copilot.eval.retrieval`: gold pages from FinanceBench evidence, strict scoring of predictions files, and the first-pages baseline.
  - The `poe eval-retrieval` and `poe compare-runs` commands; the guide [evaluation-statistics.md](concepts/evaluation-statistics.md) and the runbook [running-evaluations.md](runbooks/running-evaluations.md).
- **Commands:** `uv add numpy`, `uv run poe eval-retrieval --baseline first-pages`, `uv run poe check`.
- **Results:**
  - The first-pages baseline (the first 20 pages of the correct document) on dev: hit@20 = 0.29 (95% interval 0.20 to 0.38), recall@10 = 0.197 (0.123 to 0.277), MRR@10 = 0.075 (0.041 to 0.117). Metrics-generated questions score 0, because financial statements sit beyond page 20 of a 10-K; novel-generated questions reach hit@20 = 0.70, because many are about short 8-Ks and earnings releases.
  - Asking for the test split without `--allow-test` stops with exit code 2.
  - 104 tests pass offline, 42 of them new; mypy strict is clean.
- **Problems and fixes:**
  - **Identical intervals for different seeds.** With 0/1 scores at n = 50, every resampled mean is a multiple of 0.02, so two seeds often give the same interval and a seeding test failed. It now uses graded scores.
  - **mypy and powers of two.** `2**n` is typed as `Any`, because a negative exponent would give a float, so McNemar's tail now divides by `1 << n`.
- **Decisions:** [ADR-0007](decisions/0007-evaluation-statistics.md).
- **Next:** the routing eval set (step 1.8). The SEC steps (1.3 to 1.6) and the SQL set (1.7) wait for the SEC contact in `.env`.

### 2026-10-17 · Phase 1 · FinanceBench data and splits

- **Goal:** fix the benchmark questions and the held-out test set before writing any retrieval code (steps 1.1 and 1.2).
- **Done:**
  - `copilot.eval.financebench`: typed records for questions, evidence and documents; a manifest of the pinned commit's files with their sizes and git blob ids; downloads that are checked before anything is written, so a rerun resumes safely.
  - Fetched the question files and the 84 PDFs the questions use (159 MB) into `data/raw/financebench/`.
  - `copilot.eval.splits`: a dev/test split grouped by company and stratified by question type, chosen by a fixed seed search with exact arithmetic. The test side loads only with `allow_test=True`, and both sides are checked against recorded checksums ([ADR-0006](decisions/0006-evaluation-splits.md)).
  - Wrote the [FinanceBench data card](data/financebench.md).
- **Commands:** `uv run poe fetch-financebench --refresh-manifest`, `uv run poe fetch-financebench`, `uv run poe split-financebench`, `uv run poe check`.
- **Results:**
  - 150 questions (50 of each type), 84 documents and 32 companies. The manifest lists 370 files (706 MB) at commit `cc39aeb`.
  - The split: dev has 100 questions from 20 companies and test has 50 from 12, with question types 33 / 34 / 33 and 17 / 16 / 17 (seed 14,793). Test-set SHA-256: `244383209a16…`.
  - 62 tests pass offline, 23 of them new; mypy strict is clean.
- **Problems and fixes:**
  - **Page numbering.** FinanceBench doesn't say whether `evidence_page_num` counts from 0 or 1. Comparing evidence text with page text in three PDFs settled it: all 12 passages match page index *n* (similarity at least 0.98), so it counts from 0.
  - **A split that hid a sector.** The first company-grouped split put every financials question in test. The search now also balances document types and sectors, and penalises any sector with several companies that lands entirely on one side.
  - **Licence.** The GitHub repository has no licence file, and the Hugging Face card says CC BY-NC 4.0. The data is downloaded at run time and never committed.
- **Decisions:** [ADR-0006](decisions/0006-evaluation-splits.md).
- **Next:** the evaluation harness (step 1.9), then the routing set (1.8). The SEC steps (1.3 to 1.6) wait for the SEC contact in `.env`.

### 2026-10-17 · Phase 0 · Live model check

- **Goal:** confirm the key and both model roles against the live API (step 0.8), the last Phase 0 exit criterion.
- **Done:** listed the models available to the key, confirmed the strong and fast roles, and ran one live call per role.
- **Commands:** `uv run poe models`, `uv run poe smoke`.
- **Results:**
  - The key can use 11 models, including both role models: `openai/gpt-oss-120b` (strong) and `qwen/qwen3.8-27b` (fast). Also available: `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, Llama Prompt Guard 2 (22M and 86M), Whisper and a few speech models.
  - Fast role: replied in 0.68 s (19 tokens in, 2 out, $0.000023). Strong role: replied in 0.45 s (78 in, 46 out including its reasoning, $0.000039). Neither call needed a fallback, and both costs came from LiteLLM's bundled price map.
  - Phase 0 is done: checks pass locally and in CI, the Compose services are healthy, the project page is live, and both roles answer.
- **Problems and fixes:** none.
- **Decisions:** none. Llama Prompt Guard 2 is noted as a candidate prompt-injection classifier for the Phase 6 guardrails.
- **Next:** Phase 1. FinanceBench (steps 1.1 and 1.2) and the evaluation harness (1.9) first; the SEC steps (1.3 and 1.4) need the SEC contact in `.env`.

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
