# Build plan

| | |
|---|---|
| **Project** | Filings Research Copilot |
| **Plan written** | 2026-10-15 |
| **Current phase** | Phase 3, Doc agent with cited answers (in progress) |

This is the living plan. Steps are ticked as they land, every working session gets an entry in [BUILD_LOG.md](BUILD_LOG.md), and changes to the plan are recorded in the [change log](#10-change-log) with the reason. The [status tracker](#11-status-tracker) is at the bottom.

---

## 1. What we are building

An analyst copilot for public-company filings. A user asks a question in plain English and gets an answer built from two sources, with every claim cited:

- **Filing text.** 10-K and 10-Q documents, found with hybrid search and cited to the page.
- **Reported numbers.** XBRL financial facts from SEC EDGAR, queried with Text-to-SQL.

It also drafts longer research briefs with a small crew of agents, and exposes its tools to other AI applications through an MCP server. It is measured against FinanceBench, a public benchmark of questions over real filings.

| Example question | What it needs |
|---|---|
| "What was 3M's capital expenditure in FY2018?" | Numbers (data agent) |
| "What did Netflix identify as its main competitive risks?" | Narrative (doc agent) |
| "How did R&D spending move against revenue over five years, and how did management explain it?" | Both, combined and cross-checked |
| "Write a one-page brief on this company's liquidity." | Brief crew |

## 2. Definition of done

The project is finished when all of these are true:

1. **Deployable on demand.** One command brings up a public HTTPS deployment on AWS (ECS Fargate) with per-visitor quotas and a budget alarm; one command tears it down ([ADR-0003](decisions/0003-aws-demo-windows.md)). HTTPS comes from a custom domain or CloudFront (decided in Phase 8, see §8).
2. **Grounded.** Every answer cites the filing pages or SQL it came from, and the copilot declines when the evidence isn't there.
3. **Measured.** FinanceBench held-out results, retrieval recall@k, SQL execution accuracy, routing accuracy, latency and cost per answer, all reported with 95% confidence intervals.
4. **Trained where it pays.** The domain embedder and the LoRA router are fine-tuned and compared with their baselines on fixed eval sets; each is adopted only on a significant gain (Phase 7).
5. **Connected.** An MCP server that works from a standard MCP client such as Claude Desktop.
6. **Automated.** CI runs lint, types, tests and an eval gate on every pull request; deploys go through GitHub Actions with OIDC, so no AWS keys are stored.
7. **Documented.** Build log, decision records, concept guides, runbooks, README and project page are complete.

Accuracy targets are set after the Phase 2 and Phase 3 baselines, not before. A change ships when its paired improvement is statistically significant on the dev set.

## 3. Working method

Each phase runs the same loop:

1. **Scope.** Confirm the phase's steps; they often sharpen once the previous phase is done.
2. **Build in small commits.** One purpose per commit, [Conventional Commits](https://www.conventionalcommits.org/) messages, tests passing. Phase 0 bootstraps `main` directly; from Phase 1, work lands through pull requests from `phase-N/<topic>` branches once CI passes ([ADR-0004](decisions/0004-tooling-and-workflow.md)).
3. **Test and measure.** Unit tests for code; eval runs for anything that changes quality.
4. **Document as we go.** Log entry, decision records, and a concept guide for each new component (see §4).
5. **Review.** Each phase ends with a demo, the numbers, and a list of open questions.
6. **Publish.** The project page is updated at phase milestones.

## 4. Documentation system

Everything lives in `docs/` next to the code, so it is versioned and reviewed with the code ([ADR-0002](decisions/0002-documentation-system.md)).

| What | Where | When it's written |
|---|---|---|
| Build log | [BUILD_LOG.md](BUILD_LOG.md) | Every working session: what changed, commands, results, problems, next steps |
| Decision records (ADRs) | [decisions/](decisions/README.md) | Whenever there is a choice between real alternatives |
| Concept guides | [concepts/](concepts/README.md) | When a component lands: what it is, how it works here, how it was measured |
| Data cards | [data/](data/README.md) | When a dataset is added: source, licence, size, checksum, splits |
| Eval reports | [eval/](eval/README.md) | Every experiment: setup, numbers with confidence intervals, decision |
| Runbooks | [runbooks/](runbooks/README.md) | When something becomes operable: run, deploy, roll back, tear down |
| Glossary | [glossary.md](glossary.md) | New terms as they appear |
| Project page | [site/index.html](site/index.html) | At milestones; deployed to GitHub Pages |

## 5. Prerequisites and accounts

| Item | Status | Needed by | Notes |
|---|---|---|---|
| Python 3.12, uv, git, Docker | Installed | Phase 0 | |
| GitHub CLI, authenticated | Installed | Phase 0 | |
| Groq API key | Added | Phase 0 (step 0.8) | In `.env`; verified live on 2026-10-17 |
| SEC EDGAR contact for the User-Agent header | Added | Phase 1 | In `.env`; sent only to sec.gov |
| Hugging Face account and token | Pending | Phase 7 | Publishing models (FinanceBench comes from GitHub) |
| Langfuse Cloud (free tier) | Pending | Phase 6 | Tracing |
| Kaggle or Colab GPU (free tier) | Pending | Phase 7 | Fine-tuning |
| Qdrant Cloud free cluster | Pending | Phase 8 | Docker until then |
| Terraform, AWS CLI v2 | Not installed | Phase 8 | |
| AWS account with MFA and a budget alarm | Pending | Phase 8 | |
| Domain name (or CloudFront) for HTTPS | To decide | Phase 8 | ACM only issues certificates for names we control, so the load balancer's own `*.elb.amazonaws.com` address can't serve trusted HTTPS |

## 6. Technical choices

Starting points, each confirmed by an ADR when its phase lands.

| Area | Choice | Why | Confirmed in |
|---|---|---|---|
| Packaging and tasks | uv with a lockfile, hatchling, `src/` layout, Python 3.12; `poethepoet` tasks | Fast, reproducible, same commands on every OS | [ADR-0004](decisions/0004-tooling-and-workflow.md) |
| Config | `pydantic-settings`; `.env` locally, Secrets Manager on AWS | Typed config, no keys in code | Phase 0 |
| LLM access | LiteLLM router behind one gateway: model roles, fallbacks, cost tracking | Provider-agnostic; one place for retries and accounting | [ADR-0005](decisions/0005-llm-gateway.md) |
| PDF parsing | `pypdfium2` page text; table-aware parsing deferred, since numbers come from XBRL | Permissive licence (PyMuPDF is AGPL); 126 of 127 dev evidence pages line up | [ADR-0009](decisions/0009-pdf-parsing.md) |
| Chunking | One chunk per page, long pages split within the page; token windows, semantic and late chunking measured against it | Ranks the evidence page first most often, and citations are exact pages | [ADR-0011](decisions/0011-retrieval-baseline.md) |
| Embeddings | `BAAI/bge-small-en-v1.5` via FastEmbed (ONNX, CPU) | Runs on a laptop CPU; fine-tuned in Phase 7 | Phase 2 |
| Keyword search | BM25 sparse vectors (FastEmbed `Qdrant/bm25`) | Exact terms such as tickers and line items | Phase 2 |
| Vector database | Qdrant: dense and sparse named vectors, payload indexes; rank fusion done in our code | Dense and keyword search on one point; free cloud tier | [ADR-0010](decisions/0010-vector-store-and-embeddings.md) |
| Reranker | None in the baseline: MiniLM-L6, jina-turbo and bge-reranker-base didn't beat dense search; re-tested after query rewriting | Measured on FinanceBench dev | [ADR-0011](decisions/0011-retrieval-baseline.md); Phase 3 |
| Numbers | SEC company facts → SQLite for the curated companies; Postgres in production | text2sql-analyst runs on SQLite as-is | [ADR-0008](decisions/0008-xbrl-normalisation.md); Phase 8 |
| App state | Postgres: the Compose container locally (127.0.0.1:5433), RDS on AWS. LangGraph checkpoints (Phase 5), feedback (Phases 6 and 9), and testing the Postgres executor for the facts tables (Phase 8). No code uses it in Phase 0 | One engine locally and in production | Phases 5, 6 and 8 |
| Data agent | text2sql-analyst, an earlier project, as a pinned dependency | Reuses a tested pipeline | Phase 4 |
| Orchestration | LangGraph state graph with a checkpointer | Routing, loops, streaming, human-in-the-loop | Phase 5 |
| API and UI | FastAPI with SSE streaming; Streamlit as a thin client | Python end to end | Phase 6 |
| MCP | Official MCP Python SDK | Works with standard MCP clients | Phase 6 |
| Observability | Langfuse Cloud traces; JSON logs | Per-step latency, tokens and cost | Phase 6 |
| Evaluation | Own harness, an LLM judge checked against human labels, bootstrap CIs, paired permutation tests | Deterministic retrieval metrics; fair comparisons | [ADR-0007](decisions/0007-evaluation-statistics.md) |
| Infrastructure | Docker Compose locally; Terraform → ECS Fargate, RDS, S3, SQS, DynamoDB, Secrets Manager, CloudWatch, in demo windows | Production shape without paying for idle time | [ADR-0003](decisions/0003-aws-demo-windows.md) |
| CI/CD | GitHub Actions pinned to commit SHAs; a checksum-verified gitleaks scan of the full history; Dependabot updates; AWS access through OIDC | No long-lived keys; reproducible pipelines | Phases 0 and 8 |

Repository layout. Folders are created when their phase lands:

```text
filings-research-copilot/
├── src/copilot/
│   ├── config.py     # typed settings                         (Phase 0)
│   ├── logs.py       # structured logging                     (Phase 0)
│   ├── llm/          # gateway, model roles, fake for tests   (Phase 0)
│   ├── ingest/       # SEC client and universe (Phase 1); parsers, chunkers, indexer (Phase 2)
│   ├── facts/        # XBRL facts database, canonical metrics, cross-checks (Phase 1)
│   ├── retrieval/    # hybrid search, fusion, reranking       (Phase 2)
│   ├── sql/          # text2sql-analyst adapter, value linking (Phase 4)
│   ├── agents/       # LangGraph graph, router, validator     (Phase 5)
│   ├── api/          # FastAPI app, streaming, quotas, cache  (Phase 6)
│   ├── mcp/          # MCP server                             (Phase 6)
│   └── eval/         # datasets, metrics, judges, statistics  (Phase 1)
├── app/              # Streamlit UI                           (Phase 6)
├── training/         # fine-tuning scripts and notebooks      (Phase 7)
├── infra/            # Dockerfiles (Phase 6); Terraform       (Phase 8)
├── eval/             # question sets, results, summaries      (Phase 1)
├── data/             # downloads and built databases (git-ignored), except
│   └── reference/    #   small committed files: manifests, mappings (Phase 1)
├── scripts/          # one-off and operational scripts
├── tests/
└── docs/
```

---

## 7. Phases

Size is relative: S < M < L.

### Phase 0: Foundations (S)

**Goal:** a repository where every later phase lands cleanly.

- [x] 0.1 Initialise git and create the public GitHub repository (MIT licence).
- [x] 0.2 Package skeleton with uv (hatchling build, `src/copilot` layout) and a committed lockfile.
- [x] 0.3 Quality gates: ruff (lint and format), mypy in strict mode, pytest with `integration` and `eval` markers (unit tests cannot reach the network), pre-commit hooks.
- [x] 0.4 Typed settings with `pydantic-settings`, `.env.example`, structured logging with structlog.
- [x] 0.5 LLM gateway v0 on LiteLLM's router: model roles, retries, fallbacks, token and cost accounting, reasoning-tag splitting, and a fake LLM for tests.
- [x] 0.6 Docker Compose with Qdrant and Postgres, bound to 127.0.0.1, with health checks.
- [x] 0.7 CI on GitHub Actions (lint, format, types, tests, a full-history gitleaks scan), Dependabot updates, and a GitHub Pages deploy for the project page.
- [x] 0.8 Check which models the Groq key can use (`uv run poe models`), confirm the strong and fast roles, and run the live smoke test (`uv run poe smoke`).

**Done when:** checks pass locally and in CI, the Compose services are healthy, the project page is live on GitHub Pages, and the smoke test gets a reply from each role.
**Docs:** [ADR-0004](decisions/0004-tooling-and-workflow.md), [ADR-0005](decisions/0005-llm-gateway.md), guide [llm-gateway.md](concepts/llm-gateway.md), runbooks [local-setup.md](runbooks/local-setup.md) and [publishing-the-project-page.md](runbooks/publishing-the-project-page.md).
**Manual steps:** add the Groq key to `.env`. Once, after the repository is created: set Pages to deploy from GitHub Actions (see the publishing runbook).

### Phase 1: Data and evaluation sets (M)

**Goal:** fix the questions the system will be judged on before writing retrieval code.

- [x] 1.1 Download the FinanceBench public sample (questions, answers, evidence pages, PDFs); check its licence; write a data card.
- [x] 1.2 Split it into dev (100) and held-out test (50), grouped by company and stratified by question type ([ADR-0006](decisions/0006-evaluation-splits.md)). Record the test-set checksum before any tuning; the test set is only opened at milestones.
- [x] 1.3 Build the company universe from FinanceBench's companies; map names to tickers and CIKs with SEC's `company_tickers.json`. All 40 companies in its document list are matched: 32 by normalised name, 6 by ticker and 2 delisted ones by CIK ([companies.csv](../data/reference/companies.csv)).
- [x] 1.4 Fetch XBRL company facts (declared User-Agent, at most 10 requests per second); normalise into `companies`, `filings` and `facts` tables ([ADR-0008](decisions/0008-xbrl-normalisation.md), [data card](data/sec-company-facts.md)).
- [x] 1.5 Build a `metrics` table that maps canonical metrics (revenue, net income, capex, R&D and so on) to the tags each company actually uses; test a sample against FinanceBench answers. 28 metrics; all 33 dev metrics questions, as formulas, match exactly ([report](../eval/results/facts/financebench-dev-checks.md)).
- [x] 1.6 Write a data dictionary and table descriptions for the SQL agent ([dictionary](data/facts-dictionary.md); [descriptions](../data/reference/facts_descriptions.json) in text2sql-analyst's format).
- [x] 1.7 SQL eval set: 42 questions, 32 with verified gold SQL and 10 unanswerable, split into dev (28) and held-out test (14) ([data card](data/sql-set.md)).
- [x] 1.8 Routing eval set: 198 labelled queries across six routes (66 hand-written seeds plus two reviewed paraphrases each), split by seed into dev (138) and held-out test (60); data card [routing-set.md](data/routing-set.md).
- [x] 1.9 Eval harness: loaders, metrics (recall@k, hit@k, MRR), bootstrap CIs, paired permutation and McNemar tests, Holm adjustment, result writers ([ADR-0007](decisions/0007-evaluation-statistics.md)). Execution and routing accuracy plug in with their eval sets (1.7, 1.8).

**Done when:** every dataset has a data card and checksum, the facts tables pass their cross-checks, and the harness scores dummy predictions.
**Docs:** ADRs on eval-first splits ([ADR-0006](decisions/0006-evaluation-splits.md)), evaluation statistics ([ADR-0007](decisions/0007-evaluation-statistics.md)) and XBRL normalisation ([ADR-0008](decisions/0008-xbrl-normalisation.md)); guides [xbrl-and-financial-metrics.md](concepts/xbrl-and-financial-metrics.md) and [evaluation-statistics.md](concepts/evaluation-statistics.md); data cards [financebench.md](data/financebench.md), [routing-set.md](data/routing-set.md), [sec-company-facts.md](data/sec-company-facts.md) and [sql-set.md](data/sql-set.md); runbook [running-evaluations.md](runbooks/running-evaluations.md).
**Manual steps:** spot-check 20 random metric values against the filings ([sheet](data/facts-spot-check.md); done: the owner reported no discrepancies on 2026-10-17); add the SEC contact to `.env` (done).

### Phase 2: Ingestion and retrieval baseline (L)

**Goal:** choose the retrieval setup by measurement.

- [x] 2.1 Parse PDFs to page text with page numbers; strip running headers and footers; tag pages with their 10-K item (1A, 7, 8 and so on). pypdfium2 ([ADR-0009](decisions/0009-pdf-parsing.md)); 126 of 127 dev evidence pages line up.
- [x] 2.2 Pluggable chunkers: token-recursive with overlap, page-level, semantic, late chunking. Every chunk keeps company, year, form, section and page span.
- [x] 2.3 Index into Qdrant: dense and BM25 sparse vectors, payload indexes, recorded HNSW settings, idempotent upserts keyed by content hash. Ingestion runs as jobs (a local runner now, an SQS runner in Phase 8). [ADR-0010](decisions/0010-vector-store-and-embeddings.md).
- [x] 2.4 Retrieval variants: dense, BM25, hybrid (RRF), then cross-encoder reranking, then neighbouring chunks. None beat dense search on FinanceBench dev ([report](eval/retrieval-baseline.md)).
- [x] 2.5 Evaluate on FinanceBench dev evidence pages: page recall@5/10/20 and MRR, changing one thing at a time, with confidence intervals and latency ([report](eval/retrieval-baseline.md)).
- [x] 2.6 Pick the baseline configuration. Generate synthetic question→chunk pairs from training documents only, for Phase 7. Baseline: dense search over page chunks ([ADR-0011](decisions/0011-retrieval-baseline.md)); 1,006 pairs from 195 training filings ([data card](data/synthetic-pairs.md)).

**Done when:** a retrieval report shows the chosen setup and its significant gain over dense-only search, or explains why there isn't one.
**Docs:** ADRs on parser ([ADR-0009](decisions/0009-pdf-parsing.md)), vector store ([ADR-0010](decisions/0010-vector-store-and-embeddings.md)) and the retrieval baseline ([ADR-0011](decisions/0011-retrieval-baseline.md)); guides [chunking.md](concepts/chunking.md), [late-chunking.md](concepts/late-chunking.md), [hybrid-search-and-rrf.md](concepts/hybrid-search-and-rrf.md), [reranking.md](concepts/reranking.md), [hnsw-and-qdrant.md](concepts/hnsw-and-qdrant.md), [retrieval-metrics.md](concepts/retrieval-metrics.md); runbook [ingesting-filings.md](runbooks/ingesting-filings.md); [retrieval report](eval/retrieval-baseline.md).

### Phase 3: Doc agent with cited answers (M)

**Goal:** correct, cited answers from filing text, or an honest refusal.

- [x] 3.1 Query understanding: company, fiscal period and form become Qdrant filters. Rule-based; across all filings, recall@10 rises from 0.415 to 0.570 ([guide](concepts/query-understanding.md)).
- [ ] 3.2 Query rewriting: multi-query, HyDE and decomposition, run in parallel and fused.
- [ ] 3.3 Context building: rerank, add neighbouring chunks, pack to a token budget.
- [ ] 3.4 Grounded generation with numbered sources and inline citations; a relevance check first, and abstention when evidence is missing.
- [ ] 3.5 Calculator tool: the model writes the expression and a safe evaluator computes it.
- [ ] 3.6 LLM judge for answer correctness, with about 40 answers labelled by hand to measure how often the judge agrees with a person.
- [ ] 3.7 Dev evaluation: correctness, faithfulness, citation precision, refusal rate, latency and cost; error analysis.

**Done when:** dev results with confidence intervals and the top error categories are documented.
**Docs:** ADRs on answer format and judge design; guides `query-rewriting.md`, `grounded-generation.md`, `llm-as-judge.md`, `corrective-rag.md`.

### Phase 4: Data agent with Text-to-SQL (M)

**Goal:** reliable numbers from XBRL facts.

- [ ] 4.1 Add text2sql-analyst as a pinned dependency and index the facts schema.
- [ ] 4.2 Value linking: map company names, tickers and metric synonyms to canonical values, and contribute it back to text2sql-analyst.
- [ ] 4.3 Fiscal-calendar handling (fiscal vs calendar years, quarters).
- [ ] 4.4 Wrap the pipeline as a tool with a typed result: rows, SQL, statistics, chart spec.
- [ ] 4.5 Execution accuracy on the SQL set; error analysis and fixes.
- [ ] 4.6 Prototype hybrid answers that combine numbers with narrative.

**Done when:** execution accuracy is reported with a confidence interval, and the hybrid prototype handles 10 hand-picked questions.
**Docs:** ADR on reusing text2sql-analyst; guides `text-to-sql-agent.md`, `value-linking.md`.

### Phase 5: Orchestration with LangGraph (L)

**Goal:** one copilot that routes, combines, checks and remembers.

- [ ] 5.1 The graph: rewrite follow-up → understand → route → doc / data / hybrid / brief / small talk / decline → synthesise → validate → respond, with streamed events.
- [ ] 5.2 Router v1: an LLM router (also the teacher for Phase 7) and a semantic router over labelled examples; compare accuracy, latency and cost.
- [ ] 5.3 Validator loop: claim-level faithfulness check, retry with feedback at most twice, then abstain.
- [ ] 5.4 Self-consistency for numeric answers, kept only if the gain justifies the cost.
- [ ] 5.5 Memory: conversation state in a checkpointer; long-term memory in the Mem0 style (extract, compare, then add, update, delete or skip).
- [ ] 5.6 End-to-end dev evaluation plus agent metrics (steps per task, tool success rate, cost per task).

**Done when:** end-to-end dev results are in and every node shows up in a trace.
**Docs:** ADRs on graph design and routing; guides `langgraph-orchestration.md`, `semantic-routing.md`, `validator-loop.md`, `self-consistency.md`, `agent-memory.md`.

### Phase 6: API, UI, MCP and observability (M)

**Goal:** something people and other AI tools can use.

- [ ] 6.1 FastAPI: `/v1/ask` (SSE), `/v1/brief`, `/v1/feedback`, `/v1/sources/{id}`, health and readiness endpoints; request IDs; OpenAPI docs.
- [ ] 6.2 Guardrails: persistent per-visitor quotas, input limits, a semantic cache, filing text passed as quoted data, a read-only database role.
- [ ] 6.3 Streamlit UI: streaming chat, a citation drawer with page previews, charts, SQL details, "interpreted as" for follow-ups, feedback buttons, a trace view and an eval dashboard.
- [ ] 6.4 MCP server: tools (`search_filings`, `query_financials`, `ask_copilot`), filing pages as resources, a company-comparison prompt; tested in Claude Desktop.
- [ ] 6.5 Langfuse traces (a span per node, with tokens and cost) and latency metrics.
- [ ] 6.6 Dockerfiles for the api, ui and mcp services, and the full stack in Docker Compose.

**Done when:** the full local demo runs from one Compose command, the MCP server works in an MCP client, and traces appear in Langfuse.
**Docs:** ADRs on API/streaming and observability; guides `sse-streaming.md`, `mcp-server.md`, `semantic-cache.md`, `prompt-injection.md`, `observability.md`.

### Phase 7: Fine-tuning and optimisation (L)

**Goal:** make it better and cheaper, and prove each change.

Every experiment gets a before/after on fixed eval sets, an eval report and an adopt-or-reject ADR.

- [ ] 7.1 Domain embedder: MNRL with hard negatives on the synthetic pairs (training documents only), trained on a free GPU; ONNX export; published on Hugging Face.
- [ ] 7.2 LoRA router: a BERT-family classifier with LoRA (CPU is enough), compared with the semantic and LLM routers.
- [ ] 7.3 DSPy optimisation of one prompt (answer synthesis or HyDE), adopted only on a significant gain.
- [ ] 7.4 Stretch: a fine-tuned reranker, or a small distilled query-rewriter served on CPU.
- [ ] 7.5 Bandit model routing: replay eval logs offline with decaying ε (reward = judge score minus a cost penalty), then a feature flag online.
- [ ] 7.6 Brief crew: a Self-Discover plan, parallel section writers, an editor and a critic; optionally a jury of small models with a judge; rubric evaluation.

**Done when:** each experiment has its report and ADR, and adopted models run behind flags.
**Docs:** guides `contrastive-finetuning.md`, `lora-classifier.md`, `dspy.md`, `bandit-routing.md`, `research-briefs.md`.

### Phase 8: Production deployment on AWS, in demo windows (L)

**Goal:** a production-shaped deployment that comes up for a demo and goes away afterwards ([ADR-0003](decisions/0003-aws-demo-windows.md)).

- [ ] 8.1 Install Terraform and the AWS CLI. Create the budget alarm before any other resource; MFA on the account; a GitHub OIDC deploy role.
- [ ] 8.2 Slim, non-root container images; ECR with scan-on-push.
- [ ] 8.3 Terraform in two layers. **Persistent:** state bucket, ECR repositories, S3 data bucket, budget alarm, OIDC role, and the HTTPS front door chosen in §8 (an ACM certificate for a domain, or a CloudFront distribution). **Demo:** VPC with public subnets only (no NAT gateway), ECS services (api, ui, mcp), an SQS-driven ingestion worker, a load balancer, RDS Postgres restored from a snapshot, SQS with a dead-letter queue, DynamoDB quotas, Secrets Manager, CloudWatch logs, dashboards and alarms.
- [ ] 8.4 Move the facts tables to Postgres and add a Postgres executor for the data agent; ingest into Qdrant Cloud and keep collection snapshots in S3.
- [ ] 8.5 `demo-up` and `demo-down` tasks; a scheduled CI job tears the demo layer down if it is left running past a time limit.
- [ ] 8.6 CD: build and push, deploy, smoke tests; roll back to the previous task definition when needed.
- [ ] 8.7 Load test with Locust and size the services from the results.
- [ ] 8.8 Security pass: least-privilege roles, security groups, a read-only SQL user, dependency and image scans.
- [ ] 8.9 Measure and document the cost of one demo window.

**Done when:** `demo-up` produces a working public URL, dashboards and alarms work, and `demo-down` leaves only the persistent layer.
**Docs:** ADRs on AWS topology and CI/CD; runbooks for demo-up, demo-down, rollback, key rotation and provider outages; guides `ecs-fargate.md`, `terraform-basics.md`, `github-oidc.md`.
**Manual steps:** AWS account access; a domain, if that HTTPS option is chosen.

### Phase 9: Online evaluation and feedback (M)

**Goal:** keep quality visible over time.

- [ ] 9.1 A nightly eval job (GitHub Actions against the local stack, or during demo windows) with regression alerts and a trend chart.
- [ ] 9.2 Feedback stored as preference pairs (chosen vs rejected) for future preference tuning.
- [ ] 9.3 Bandit routing online, with a cost guardrail.
- [ ] 9.4 Stretch: a search page that interleaves two retrievers and logs clicks.
- [ ] 9.5 Drift checks on retrieval scores, refusal rate and latency.

**Done when:** the nightly trend is visible and feedback is being stored.
**Docs:** guides `online-evaluation.md`, `preference-data.md`.

### Phase 10: Showcase and polish (M)

**Goal:** a finished, verifiable project.

- [ ] 10.1 Final README: architecture, results with confidence intervals, limitations, cost per demo.
- [ ] 10.2 Demo video recorded during a demo window; screenshots.
- [ ] 10.3 Project page updated with measured numbers and links.
- [ ] 10.4 A technical write-up of what worked and what didn't.
- [ ] 10.5 Documentation review: every concept guide complete with review questions; all links checked.

**Done when:** every number on the README and project page links to the eval report that produced it.

---

## 8. Open decisions

| Before | Decision | Current thinking |
|---|---|---|
| Phase 8 | How to serve HTTPS | A domain we own with an ACM certificate on the load balancer, or CloudFront's default `*.cloudfront.net` certificate in front of it (no domain needed; CloudFront's origin timeout must allow streamed answers) |

Already decided: public repository with an MIT licence ([ADR-0004](decisions/0004-tooling-and-workflow.md)); AWS runs in demo windows ([ADR-0003](decisions/0003-aws-demo-windows.md)); the SEC contact is the owner's name and email, kept in `.env`.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Free-tier rate limits on Groq | LiteLLM fallbacks, semantic cache, per-visitor quotas |
| LLM output varies between runs | Repeated eval runs and confidence intervals |
| Models may have seen FinanceBench or well-known filings in training | Held-out split; synthetic questions on recent filings; memorisation noted alongside results |
| XBRL tags differ across companies | A canonical `metrics` mapping with tests |
| PDF tables flatten badly | Table-aware parsing experiment; numbers come from XBRL instead |
| Development machine has no CUDA GPU | Train on Kaggle or Colab GPUs; serve small models on CPU with ONNX |
| AWS costs | Budget alarm first; demo windows; scheduled auto-teardown |
| Qdrant Cloud free clusters may pause when idle | Collection snapshots in S3; restore during `demo-up` |
| FinanceBench licence | Used for evaluation only; licence checked in Phase 1 |
| Scope | Each phase delivers standalone value; stretch items are marked |

## 10. Change log

| Date | Change | Why |
|---|---|---|
| 2026-10-15 | Plan created | [ADR-0001](decisions/0001-choose-filings-research-copilot.md) |
| 2026-10-15 | AWS runs in demo windows; Phase 8 split into persistent and demo layers | [ADR-0003](decisions/0003-aws-demo-windows.md) |
| 2026-10-15 | Postgres container published on host port 5433 | A local PostgreSQL install already held 5432 |
| 2026-10-15 | Project page deployed with GitHub Pages | A stable public URL |
| 2026-10-15 | HTTPS needs a domain or CloudFront (decided in Phase 8) | ACM cannot issue certificates for the load balancer's AWS-owned address |
| 2026-10-15 | Definition of done item 4: fine-tuned components are adopted only on a significant gain | Matches the rule that every change must earn its place |
| 2026-10-15 | Local services bound to 127.0.0.1; Postgres documented as app state | Pre-push review |
| 2026-10-17 | FinanceBench split grouped by company as well as stratified by question type | Keeps every test company's filings out of tuning and Phase 7 training ([ADR-0006](decisions/0006-evaluation-splits.md)) |
| 2026-10-17 | Table-aware PDF parsing deferred | Reported numbers come from XBRL; pdfium's page text lines up with the evidence pages ([ADR-0009](decisions/0009-pdf-parsing.md)) |
| 2026-10-18 | Retrieval baseline is dense search over page chunks; hybrid search and reranking are re-tested in Phase 3 after query rewriting | Neither beat dense search on FinanceBench's templated questions ([ADR-0011](decisions/0011-retrieval-baseline.md)) |
| 2026-10-17 | Table-aware PDF parsing deferred | Reported numbers come from XBRL; pdfium's page text lines up with the evidence pages ([ADR-0009](decisions/0009-pdf-parsing.md)) |
| 2026-10-18 | Retrieval baseline is dense search over page chunks; hybrid search and reranking are re-tested in Phase 3 after query rewriting | Neither beat dense search on FinanceBench's templated questions ([ADR-0011](decisions/0011-retrieval-baseline.md)) |

## 11. Status tracker

| Phase | Status | Started | Finished |
|---|---|---|---|
| 0 Foundations | Done | 2026-10-15 | 2026-10-17 |
| 1 Data and evaluation sets | Done | 2026-10-17 | 2026-10-17 |
| 2 Ingestion and retrieval baseline | Done | 2026-10-17 | 2026-10-18 |
| 3 Doc agent | In progress | 2026-10-19 | |
| 4 Data agent | Planned | | |
| 5 Orchestration | Planned | | |
| 6 API, UI, MCP, observability | Planned | | |
| 7 Fine-tuning and optimisation | Planned | | |
| 8 AWS deployment (demo windows) | Planned | | |
| 9 Online evaluation | Planned | | |
| 10 Showcase and polish | Planned | | |
