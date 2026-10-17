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

### 2026-10-17 · Phase 2 · Parsing filings

- **Goal:** page-accurate, clean text for every filing, tagged with the section each page is in (step 2.1).
- **Done:**
  - Recorded the owner's review of the 20-value spot check from Phase 1: no discrepancies.
  - `copilot.ingest.pdf`: pdfium text extraction, running header and footer removal, and section tagging (10-K items, 10-Q parts and items, 8-K items).
  - `copilot.ingest.corpus`: resumable parsing in worker processes, with a manifest of parser version and PDF git blob ids.
  - `poe parse-pdfs` and `poe check-pages`; [ADR-0009](decisions/0009-pdf-parsing.md) and the [ingestion runbook](runbooks/ingesting-filings.md).
- **Commands:** `uv run poe parse-pdfs`, `uv run poe check-pages`, a pypdfium2 against pypdf benchmark, `uv run poe check`.
- **Results:**
  - 84 documents, 12,013 pages, parsed in 25 seconds with 8 processes; 82 pages are images with no text. 91% of 10-K pages carry a section tag; the rest are front matter.
  - 126 of 127 dev evidence passages line up with the parsed page of the same index, with a median word overlap of 0.99.
  - pypdfium2 parses 85 to 101 pages a second on one core against pypdf's 9, and matches FinanceBench's page text more closely (median overlap 1.000 against 0.987).
  - 228 tests pass offline, 19 of them new; two integration tests parse a real filing.
- **Problems and fixes:**
  - **Diluted headers.** PepsiCo's 2021 10-K runs to 549 pages with its exhibits, so "Table of Contents" heads only 24% of them and slipped under a 25% threshold. The threshold is now 10% of pages, with a floor of 5 pages so that short 8-Ks keep table titles repeated on 3 pages.
  - **What must never be stripped.** Lowering the threshold would have removed table rows from Johnson & Johnson's 8-K and Microsoft's running "Item 7" headers, which section tagging needs. Lines with more than two numbers, item and part headings, and unit lines such as "(dollars in millions)" are now always kept, with "Form 10-K" not counting as a number, so footers like "2019 FORM 10-K 45" still go.
  - **Tables of contents.** Contents pages list every item, and some continue onto a second page. A page with two or more item lines ending in a page number, or four or more item headings, is treated as a table of contents.
  - **Encrypted PDFs.** 39 of the 84 PDFs are AES-encrypted. pdfium opens them; pypdf needed an extra package just to read them.
- **Decisions:** [ADR-0009](decisions/0009-pdf-parsing.md).
- **Next:** chunking (step 2.2).

### 2026-10-17 · Phase 1 · Phase 1 complete

- **Goal:** confirm Phase 1's exit criteria and publish the milestone.
- **Done:**
  - **Every dataset has a data card and checksum:** FinanceBench (a manifest of git blob ids, and SHA-256 for each side of the split), the routing set and the SQL set (SHA-256 for each side), and the SEC company facts (a manifest with the SHA-256 of all 81 files).
  - **The facts tables pass their cross-checks:** all 33 FinanceBench dev metrics questions, as formulas, match exactly.
  - **The harness scores dummy predictions:** first-pages retrieval, keyword and majority routing, and gold and decline-all SQL, each with 95% intervals.
  - Generated a [spot-check sheet](data/facts-spot-check.md) of 20 random annual values with links to their filings, for the manual check the plan asks for.
  - Updated the plan, the README and the project page.
- **Commands:** `uv run poe spot-check-facts`, `uv run poe check`.
- **Results:** floors on dev to beat in later phases: retrieval hit@20 0.29 (Phase 2), routing accuracy 0.623 (Phase 5), SQL accuracy 0.250 when declining everything (Phase 4).
- **Problems and fixes:** none new.
- **Decisions:** none.
- **Next:** Phase 2, the ingestion and retrieval baseline: parse the FinanceBench PDFs page by page, chunk them, index them in Qdrant with dense and BM25 vectors, and measure page recall on the dev evidence pages.

### 2026-10-17 · Phase 1 · SQL eval set

- **Goal:** questions the data agent will be judged on, with verified gold SQL, including some it should decline (step 1.7).
- **Done:**
  - Wrote 42 questions by hand: 32 with gold SQL across lookups, rankings, ratios, aggregates, trends, provenance, comparisons and growth, and 10 that the database can't answer.
  - Ran every gold query and compared its result with the companies' reported figures.
  - `copilot.eval.sql`: building the set, a split by category, the held-out guard and checksums, a row comparator with text2sql-analyst's rules, and scoring on a read-only connection with a step limit; `poe build-sql-set` and `poe eval-sql`.
  - Wrote the [SQL-set data card](data/sql-set.md).
- **Commands:** `uv run poe build-sql-set`, `uv run poe eval-sql --baseline gold`, `uv run poe eval-sql --baseline decline-all`, `uv run pytest -m integration`, `uv run poe check`.
- **Results:**
  - Dev has 28 questions (21 answerable) and test has 14 (11 answerable).
  - Gold SQL scores 1.000 on dev, which checks the scorer; declining everything scores 0.250 (95% interval 0.107 to 0.429).
  - 209 tests pass offline, 20 of them new; the integration test re-runs every gold query against the real database and passes.
- **Problems and fixes:**
  - **A 127% net margin.** Reviewing the gold results showed General Mills earning more than its revenue. It tags a partial $2 billion `Revenues` figure beside $19 billion of sales, and `Revenues` ranked first. Revenue now takes the largest figure among its tags, which changed 12 company-years and fixed American Express too, whose contract revenue had been taken instead of its total. All 33 FinanceBench cross-checks still agree.
  - **No operating income for Pfizer.** Pfizer's income statement has no operating-income line, so that question moved to Microsoft.
- **Decisions:** none new; ADR-0008 records the revenue rule.
- **Next:** close Phase 1: the plan, the project page, and a sheet of 20 random values for a manual spot-check against the filings.

### 2026-10-17 · Phase 1 · Facts database

- **Goal:** turn SEC company facts into tables the SQL agent can query, with one trustworthy value per company, metric and fiscal year (steps 1.4 to 1.6).
- **Done:**
  - `copilot.facts`: flattening company facts into `facts`, `filings` and `concepts`; finding each filing's period end; deriving fiscal-year labels; 28 canonical metrics with ranked tags; `annual_values` as first reported, with the latest figure beside it ([ADR-0008](decisions/0008-xbrl-normalisation.md)).
  - A safe formula evaluator, and cross-checks that rewrite all 33 FinanceBench dev metrics questions as formulas.
  - `poe build-facts` and `poe check-facts`; the [data dictionary](data/facts-dictionary.md) and table descriptions for the SQL agent; the guide [xbrl-and-financial-metrics.md](concepts/xbrl-and-financial-metrics.md).
- **Commands:** `uv run poe build-facts`, `uv run poe check-facts`, `uv run poe check`.
- **Results:**
  - `data/processed/facts.db`: 1,059,696 facts from 2,623 filings, 4,233 concepts and 15,359 annual values, built in about 20 seconds.
  - All 33 FinanceBench cross-checks match the gold answers exactly, at the precision each question asks for.
  - FY2015 to FY2023 coverage is 96 to 98% for revenue, net income, cash from operations, total assets and equity.
  - 186 tests pass offline, 39 of them new.
- **Problems and fixes:**
  - **Rounding, not errors.** The first run agreed on 28 of 33. Four misses were FinanceBench printing whole millions with two zero decimals (`$1616.00` for a filed 1,615.9). Each check now takes its precision from the question's wording.
  - **Nike's inventory tag.** Nike reports inventory as `InventoryFinishedGoodsNetOfReserves`, now a fallback tag.
  - **Finding the current period took four tries.** The most common end date failed when equity statements added older balances (Nike's FY2010). The latest end date failed on a forward-looking fact (Boeing's FY2017 10-K) and on stray contexts a day off (Foot Locker's FY2013). The final rule takes full-period facts ending by the filing date, then the most common end date within two weeks of the latest. Compared with the first rule it corrected 394 early-year values and lost none.
  - **SEC's fiscal-year labels.** Best Buy's FY2021 10-K is labelled 2020, which collided with FY2020 and dropped a year; Ulta, Foot Locker and Salesforce had similar slips. Labels now come from the period end, named the company's way (by end year, like Walmart, or by the year most days fall in, like Ulta), with the convention decided by a vote over the company's filings.
  - **A transition year.** Best Buy's 2013 10-KT covers 11 months; it now gets balance-sheet values but no annual flow values.
- **Decisions:** [ADR-0008](decisions/0008-xbrl-normalisation.md).
- **Next:** the SQL eval set (step 1.7), then close Phase 1.

### 2026-10-17 · Phase 1 · SEC client and company universe

- **Goal:** match FinanceBench's companies to SEC filers and download their XBRL company facts (step 1.3 and the fetching half of 1.4).
- **Done:**
  - Added the SEC contact to `.env`, with the owner's approval; SEC rejects requests that don't name one.
  - `copilot.ingest.sec`: an EDGAR client that refuses to start without a contact, spaces requests to 5 per second (SEC allows 10), and retries 429 and 5xx responses with backoff, honouring `Retry-After`; cached, JSON-checked downloads.
  - `copilot.ingest.universe`: name matching after normalising case, punctuation, "&" and corporate suffixes, with ticker and CIK overrides.
  - `poe fetch-sec`: writes `data/reference/companies.csv` and `data/reference/sec_manifest.json` (URL, time, size and SHA-256 of all 81 files), and caches the raw JSON.
  - Wrote the [SEC company facts data card](data/sec-company-facts.md) and the [fetching runbook](runbooks/fetching-sec-data.md).
- **Commands:** `uv run poe fetch-sec`, `uv run poe check`.
- **Results:**
  - All 40 companies matched: 32 by name, 6 by ticker override and 2 by CIK override. The 80 company files downloaded in 49 seconds: 164 MB of company facts and 11 MB of submissions.
  - 147 tests pass offline, 25 of them new.
- **Problems and fixes:**
  - **Delisted companies.** Activision Blizzard (acquired in 2023) and Foot Locker are no longer in SEC's ticker list. Both are matched by CIK, each checked against its SEC submissions record first.
  - **Names that don't match.** "AMD", "Amazon" ("AMAZON COM INC"), "Costco" ("COSTCO WHOLESALE CORP /NEW") and three more need ticker overrides; normalising handles the rest, including state tags such as "/NY".
- **Decisions:** none.
- **Next:** normalise the facts into SQLite, map canonical metrics to each company's tags, and cross-check against FinanceBench (steps 1.4 to 1.6).

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
