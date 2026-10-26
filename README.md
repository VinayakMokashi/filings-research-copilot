# Filings Research Copilot

[![CI](https://github.com/VinayakMokashi/filings-research-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/VinayakMokashi/filings-research-copilot/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An agentic research copilot for public-company filings. Ask a question about a company and get an answer built from its 10-K and 10-Q text and its XBRL financial facts, with every claim cited to the page or query it came from.

> **Status:** in active development. Phases 0 to 4 and 6 are done (foundations, data and evaluation sets, the retrieval baseline, the doc agent with cited answers, the data agent with Text-to-SQL, and the API, web UI, MCP server, container stack and traces); Phase 5's orchestration is built, with its last evaluations running; Phase 7, fine-tuning, is next, of 11 phases numbered 0–10. Progress is tracked in the [build plan](docs/PLAN.md) and the [build log](docs/BUILD_LOG.md).
>
> **Project page:** https://vinayakmokashi.github.io/filings-research-copilot/

## What it does (when finished)

- **Cited answers from filing text.** The filings a question names, three rewrites of it, and dense search over page chunks, each chosen by measurement; answers with a citation on every sentence, a calculator for arithmetic, and a refusal when the evidence isn't there. On FinanceBench dev the doc agent answers 65% of questions correctly (88% of those that ask for a figure), by an LLM judge checked against reference labels.
- **Numbers from structured data.** Text-to-SQL over XBRL company facts, built on [text2sql-analyst](https://github.com/VinayakMokashi/text2sql-analyst): hints that link the question to the database's companies and metrics, read-only guardrails, and an answer that carries its SQL, the rows, exact statistics and a chart. On FinanceBench's dev figure questions it answers 32 of 33 correctly, by the same judge, where the doc agent answers 29.
- **Research briefs.** A planner, parallel section writers, an editor and a critic, with every claim validated against its source.
- **Tools for other AI apps.** An MCP server exposing search, financial queries and the copilot itself.
- **Measured.** Evaluated on FinanceBench and purpose-built test sets, with 95% confidence intervals on every reported number.
- **Deployable on demand.** Terraform deploys a production-shaped Google Cloud stack (Cloud Run, Cloud SQL, Pub/Sub, Secret Manager). The services scale to zero, and the database runs only for demos.

## Architecture

```mermaid
flowchart LR
    C["Clients<br/>web · MCP"] --> A["API<br/>quotas · cache"]
    A --> R{Router}
    R --> D["Doc agent<br/>RAG over filings"]
    R --> T["Tools<br/>calculator · fetchers"]
    R --> B["Brief crew"]
    R --> S["Data agent<br/>Text-to-SQL"]
    D <--> Q[("Qdrant<br/>dense + BM25")]
    S <--> P[("SQL store<br/>XBRL facts")]
    D & T & B & S --> V["Validator"]
    V -- "pass" --> ANS["Answer<br/>citations · chart · SQL"]
    V -. "retry with feedback, max 2" .-> R
```

Every model call goes through one gateway (LiteLLM, with Groq first and other providers as fallback), and every step is traced in Langfuse. Details: [docs/PLAN.md](docs/PLAN.md) and the [decision records](docs/decisions/README.md).

## What's built so far

| Component | Where |
|---|---|
| Typed settings from environment and `.env` | `src/copilot/config.py` |
| Structured logging (console or JSON) | `src/copilot/logs.py` |
| LLM gateway: model roles, retries, fallbacks, cost accounting, reasoning handling, key redaction | `src/copilot/llm/` ([guide](docs/concepts/llm-gateway.md)) |
| Local Qdrant (vector store) and Postgres (app state), bound to 127.0.0.1 | `docker-compose.yml` |
| CI: lint, format, strict types, tests, a full-history secret scan | `.github/workflows/ci.yml`, `.gitleaks.toml` |
| Weekly dependency updates for Actions, `uv.lock` and pre-commit hooks | `.github/dependabot.yml` |
| FinanceBench download checked against a pinned manifest; dev/test split by company, with the test set held out | `src/copilot/eval/`, `eval/financebench/` ([data card](docs/data/financebench.md)) |
| Evaluation harness: retrieval metrics, bootstrap intervals, paired permutation tests, run reports | `src/copilot/eval/`, `eval/results/` ([guide](docs/concepts/evaluation-statistics.md), [runbook](docs/runbooks/running-evaluations.md)) |
| Routing eval set: 198 labelled questions, split by seed, with keyword and majority baselines | `eval/routing/` ([data card](docs/data/routing-set.md)) |
| SEC EDGAR client (declared contact, rate limit, retries) and the 40-company universe matched to CIKs | `src/copilot/ingest/`, `data/reference/companies.csv` ([data card](docs/data/sec-company-facts.md)) |
| Facts database: 1.06 million XBRL facts and 28 canonical metrics per company-year, matching all 33 FinanceBench dev metrics questions | `src/copilot/facts/` ([guide](docs/concepts/xbrl-and-financial-metrics.md), [dictionary](docs/data/facts-dictionary.md)) |
| SQL eval set: 42 questions with verified gold SQL or a reason to decline, and a read-only scorer | `eval/sql/`, `src/copilot/eval/sql.py` ([data card](docs/data/sql-set.md)) |
| PDF parsing: page text with running headers removed and 10-K/10-Q sections tagged | `src/copilot/ingest/pdf.py` ([ADR-0009](docs/decisions/0009-pdf-parsing.md), [runbook](docs/runbooks/ingesting-filings.md)) |
| Chunking: page-level, token windows with overlap, and semantic, each chunk carrying its pages, section and filing metadata | `src/copilot/ingest/chunking.py` |
| Qdrant index: bge-small dense and BM25 sparse vectors per chunk, payload indexes, resumable per-document jobs, and late chunking with jina-v2-small | `src/copilot/ingest/` ([ADR-0010](docs/decisions/0010-vector-store-and-embeddings.md), [HNSW guide](docs/concepts/hnsw-and-qdrant.md)) |
| Retrieval: dense, BM25 and hybrid search with client-side rank fusion, cross-encoder reranking and neighbouring chunks, each measured on FinanceBench dev; the baseline is dense search over page chunks | `src/copilot/retrieval/` ([report](docs/eval/retrieval-baseline.md), [ADR-0011](docs/decisions/0011-retrieval-baseline.md)) |
| Synthetic training pairs: 1,006 LLM-written questions paired with the chunks that answer them, from filings kept apart from evaluation | `src/copilot/training/` ([data card](docs/data/synthetic-pairs.md)) |
| Query understanding and rewriting: company, period and form resolved to filings; multi-query, HyDE and decomposition rewrites fused with the question | `src/copilot/retrieval/query.py`, `rewrite.py` ([ADR-0012](docs/decisions/0012-query-understanding-and-rewriting.md)) |
| Model-call cache and pacing for free tiers: replay by model, messages and parameters; pauses sized to the tokens each call used | `src/copilot/llm/cache.py`, `pacing.py` |
| Doc agent: numbered sources within 3,000 tokens, one JSON answer call with citations, a safe calculator, and one retry aimed at what a refusal names as missing | `src/copilot/answer/` ([ADR-0013](docs/decisions/0013-answer-format.md), [guide](docs/concepts/grounded-generation.md)) |
| Answer evaluation: an LLM judge with a rubric and code-computed comparisons of figures, checked against reference labels; faithfulness and citation precision; error categories, latency and cost | `src/copilot/eval/judge.py`, `faithfulness.py`, `errors.py` ([ADR-0014](docs/decisions/0014-answer-judge.md), [report](docs/eval/doc-agent-dev.md)) |
| Data agent: text2sql-analyst's Text-to-SQL pipeline over the facts database, with value linking (company, metric and coverage hints) and its model calls on the gateway; every SQL question answered correctly, dev and held-out test, and 32 of FinanceBench's 33 dev metrics questions. A typed answer for other components: status, SQL, rows, exact statistics and a chart spec | `src/copilot/sql/` ([ADR-0015](docs/decisions/0015-reuse-text2sql-analyst.md), [guide](docs/concepts/text-to-sql-agent.md), [value linking](docs/concepts/value-linking.md), [report](docs/eval/data-agent-financebench.md)) |
| Hybrid answers: the data agent's query result and the doc agent's pages as numbered sources for one cited answer. Version 2 routes each question by need, splits it between the agents, answers in part and retries; on 13 questions of our own it gives every expected figure for all 13, where the prototype gave them for 10 | `src/copilot/answer/hybrid.py`, `hybrid_v2.py` ([guide](docs/concepts/hybrid-answers.md), [prototype report](docs/eval/hybrid-prototype.md), [version 2 report](docs/eval/hybrid-v2.md)) |
| Router: an LLM router on gpt-oss-120b that routes every routing-set question correctly, 138 on dev and 60 on the held-out test split, at $0.0002 and half a second a question, with a semantic router (bge-small, companies and years masked, nearest route centroid; 0.74 on dev, 0.80 on test) beside it as the fallback | `src/copilot/agents/router.py` ([ADR-0017](docs/decisions/0017-routing.md), [guide](docs/concepts/semantic-routing.md), [report](docs/eval/routing.md)) |
| Orchestration: a LangGraph state graph from the question to the reply (rewrite, understand, route, the specialist, synthesise, validate, respond), with every node's start and end streamed and kept as a JSON-line trace, and conversations kept by a checkpointer, in Postgres when asked; `poe ask` runs one question through it | `src/copilot/agents/` ([ADR-0018](docs/decisions/0018-graph-design.md), [guide](docs/concepts/langgraph-orchestration.md)) |
| Validator loop: every cited sentence of a doc or hybrid answer checked by a third model before it is shown, and a failing answer revised at most twice, then trimmed to what holds or declined; faithful answers rise from 0.63 to 0.85 on FinanceBench dev, at $0.0008 an answer | `src/copilot/agents/validator.py` ([ADR-0019](docs/decisions/0019-validator-loop.md), [guide](docs/concepts/validator-loop.md), [report](docs/eval/validator-dev.md)) |
| Memory: follow-ups rewritten into standalone questions from the conversation and the user's notes; Mem0-style notes about each user (what they follow, how they want answers), kept in Postgres across conversations; every turn of a 20-turn memory set resolved | `src/copilot/agents/memory.py` ([guide](docs/concepts/agent-memory.md), [data card](docs/data/memory-set.md)) |
| API: FastAPI with the answer streamed as server-sent events (each node's start and end, the route, the reply), feedback, cited pages, health and readiness probes, request ids and OpenAPI docs | `src/copilot/api/` ([ADR-0020](docs/decisions/0020-api-and-streaming.md), [guide](docs/concepts/sse-streaming.md)) |
| Guardrails: daily question quotas per visitor and in total (429 before any model call), anonymous callers who keep no notes, instructions hidden in retrieved pages quoted out before the model reads them (none of 53,901 corpus pages flagged), and an answer cache for exact repeats; a semantic cache was measured and rejected, since it scored swapped measures above paraphrases | `src/copilot/api/quotas.py`, `cache.py`, `src/copilot/answer/injection.py` ([prompt injection](docs/concepts/prompt-injection.md), [semantic caching](docs/concepts/semantic-cache.md)) |
| Web UI: a Streamlit chat over the API that names each step as it runs, then shows the answer with its sources (a cited filing page opens in place, the facts database shows its SQL), a query's chart and table, the steps with their times, and thumbs up or down; a results page with the evaluations' headline numbers | `src/copilot/ui/` |
| MCP server: the filings' search and the facts database as tools that need no model call, the copilot itself through the API, every filing page as a resource, and a prompt for comparing companies, for MCP clients such as Claude Desktop | `src/copilot/mcp/` |
| Containers: an API image that also runs the MCP server and a UI image, from one multi-stage Dockerfile, non-root and pinned by digest; the whole stack from one Compose command, with health checks and the data mounted | `Dockerfile`, `docker-compose.yml` |
| Observability: each API run as a Langfuse trace, with a span per node and every model call's tokens and cost; latency by route and node from the traces | `src/copilot/agents/tracing.py`, `src/copilot/eval/latency.py` |

## Local development

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
cp .env.example .env          # add GROQ_API_KEY
uv run poe services-up        # Qdrant on 127.0.0.1:6333, Postgres on 127.0.0.1:5433
uv run poe check              # ruff, format check, mypy, pytest: the same steps as CI
uv run poe secrets            # gitleaks over the full history, as CI does (needs Docker)
uv run poe smoke              # one live call per model role (needs the key)
uv run poe fetch-financebench # evaluation questions and the PDFs they cite (159 MB)
uv run poe eval-retrieval --baseline first-pages   # score a retriever, with 95% intervals
uv run poe eval-routing --baseline keyword         # score a router
uv run poe fetch-sec          # SEC company facts for the 40 companies (needs SEC_USER_AGENT)
uv run poe build-facts        # the SQLite facts database; then `poe check-facts`
uv run poe eval-sql --baseline gold   # score SQL against the facts database
uv run poe parse-pdfs         # clean, section-tagged page text from the filing PDFs
uv run poe chunk-corpus --strategy tokens-480     # chunk the parsed pages
uv run poe index-corpus --strategy page --docs all   # embed chunks into Qdrant (resumable)
uv run poe run-retrieval --collection fb_page_bge-small --mode dense   # search and score on dev
uv run poe generate-pairs --per-doc 6   # synthetic question-to-chunk pairs (needs the key)
uv run poe answer-questions --run doc-agent-v4-full   # answer the dev questions (resumable; needs the key)
uv run poe judge-answers --run doc-agent-v4-full      # grade them against the reference answers
uv run poe check-faithfulness --run doc-agent-v4-full # check each sentence against its citations
uv run poe analyse-errors --run doc-agent-v4-full --judge qwen3.8-27b-p2   # error categories, latency, cost
uv run poe run-sql-agent                              # the data agent on the SQL set, scored
uv run poe ask-data "How did 3M's capital expenditure change from fiscal 2018 to fiscal 2022?"
uv run poe answer-with-data                           # FinanceBench's dev metrics questions, by SQL
uv run poe run-hybrid --agent hybrid --run hybrid-v1  # figures from SQL, reasons from the filings, one answer
uv run poe run-router --router llm --role strong --run llm-gpt-oss-120b   # route the routing set, scored
uv run poe validate-answers --source doc-agent-v4-full --run doc-agent-v4-validated   # the validator loop over stored answers
uv run poe self-consistency --source doc-agent-v4-full --k 3 --run doc-agent-v4-sc3   # a vote over sampled figure answers
uv run poe run-memory --run memory-v2                 # follow-ups and notes on the memory set, scored
uv run poe api                                        # the API on 127.0.0.1:8000, docs at /docs
uv run poe ui                                         # the web UI on 127.0.0.1:8501, over the API
uv run poe mcp                                        # the MCP server on stdio, for a desktop client
uv run poe stack-up                                   # the whole stack in Docker: API, UI and MCP server
uv run poe latency-report                             # median and 95th percentile by route and node, from traces
uv run poe ask "What was 3M's capital expenditure in 2018?"   # one question through the graph, each step shown
```

Step-by-step setup and troubleshooting: [docs/runbooks/local-setup.md](docs/runbooks/local-setup.md).

## Documentation

- [Build plan](docs/PLAN.md): phases, steps and exit criteria
- [Build log](docs/BUILD_LOG.md): what happened in each working session
- [Decision records](docs/decisions/README.md): what was chosen and why
- [Concept guides](docs/concepts/README.md): how each component works
- [Runbooks](docs/runbooks/README.md): setup and operations

## License

[MIT](LICENSE)
