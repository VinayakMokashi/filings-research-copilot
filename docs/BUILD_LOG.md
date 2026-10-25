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

### 2026-10-25 · Maintenance · FinanceBench's text out of the repository

- **Goal:** keep FinanceBench's questions and answers out of the repository: they are licensed CC BY-NC 4.0 and stay in the git-ignored `data/` directory ([data card](data/financebench.md)).
- **Done:** every tracked file was compared with the local questions, answers and justifications, six words at a time with punctuation ignored. About twenty lines from Phases 2 to 4 quoted question text, and one quoted an answer: the templates' instructions in the retrieval guides and report, questions used as examples in the guides, the data agent report and a docstring, and test inputs. They are paraphrased now, and the tests use questions written for the project.
- **Results:** what still matches is the vocabulary filings and questions share, such as "purchases of property, plant and equipment" and XBRL concept names. `poe check`: 475 passed.
- **Problems and fixes:** the first scan compared eight-word runs with punctuation kept and missed a quote that began just after an opening quotation mark; the final scan ignores punctuation. Earlier commits still hold the quotes; only rewriting the history would remove them.
- **Next:** the remaining Phase 5 runs.

### 2026-10-25 · Phase 5 · Memory

- **Goal:** follow-ups that make sense, and notes about users that carry into their next conversation (step 5.5).
- **Done:**
  - `copilot.agents.memory`: `rewrite_followup` turns a follow-up into a standalone question from the last three turns and the user's notes, on the strong role, with no call for a first question from a user without notes; `extract` and `reconcile` keep short notes about the user in the Mem0 style (add, update, delete or nothing), on the small role.
  - The graph's `rewrite` node now rewrites, and a `remember` node after `respond` updates the notes, kept in a LangGraph store: in memory, or in the Compose Postgres with `poe ask --postgres --user NAME`. Batch runs keep no notes, so single questions behave as before.
  - A memory set of our own: 10 conversations from 6 users, 20 turns ([data card](data/memory-set.md)), and `poe run-memory` to score the rewrites and the notes.
  - The [agent memory guide](concepts/agent-memory.md).
- **Commands:** `uv run poe run-memory --run memory-v2`, `uv run poe run-memory --run memory-v1 --rescore`, `uv run poe ask "..." --thread demo --postgres --user u1`.
- **Results:**
  - Every turn resolved with both notes prompts: 7 of 7 follow-ups, 2 of 2 questions answered from an earlier conversation's notes, and 10 of 11 standalone questions left as asked (the eleventh lost a preamble and still named what it must).
  - Notes, prompt 1: 15 kept, of which 6 said what users had said about themselves; 8 were inferred from questions, and one preference was made up. Its six checks, written before the run, all passed.
  - Notes, prompt 2: 6 kept, all stated by their users; 15 of 15 checks pass, against 7 of 15 for prompt 1. The checks and the prompt were both written after reading prompt 1's notes, on the same turns.
  - About $0.0002 a turn at list prices, rewrite and notes together.
- **Problems and fixes:**
  - **Asking is not following:** the first prompt's "the companies they follow or care about" turned every question into a note; the second notes only what users say about themselves.
  - **Checks that only look for what should be there** passed notes that were mostly wrong; the checks now include what mustn't be there, and `--rescore` applies them to a finished run.
  - **Random note ids** made every rerun's reconcile prompts new; an id is now a hash of the user and the note's text.
- **Decisions:** none new; the design follows step 5.5 of the plan and is explained in the guide.
- **Next:** self-consistency (step 5.4) and the end-to-end evaluation (step 5.6).

### 2026-10-25 · Phase 5 · The validator loop

- **Goal:** check every cited sentence before an answer is shown, and send what fails back to the writer at most twice (step 5.3).
- **Done:**
  - `copilot.agents.validator`: the check (the faithfulness check of Phase 3, on the `small` role, gpt-oss-20b), the revision (the writer's model and rules, with the failing sentences listed), and `trim`, which keeps the verified sentences or turns the answer into a refusal that says what couldn't be verified.
  - The graph's `validate` node checks doc and hybrid answers, and a conditional edge sends a failing one to `revise` and back, at most twice; the response reports the check. Answer records keep every source's text, since a revision may need a page the first answer didn't cite.
  - `poe validate-answers` runs the loop over a stored run, as a new run for the judges.
  - [ADR-0019](decisions/0019-validator-loop.md), the [dev report](eval/validator-dev.md) and the [validator loop guide](concepts/validator-loop.md).
- **Commands:** `uv run poe validate-answers --source doc-agent-v4-full --run doc-agent-v4-validated`, then `poe check-faithfulness` and `poe judge-answers` on that run, and `poe compare-runs` against `doc-agent-v4-full`.
- **Results:**
  - Faithful answers 0.628 to 0.848 (+0.207 on the 92 answered both times, p = 0.0001); none went from faithful to unfaithful.
  - Correct 0.65 to 0.61 (p = 0.28): figure questions unchanged at 0.879, domain-relevant questions 0.588 to 0.441 (p = 0.063), as the loop strips judgements that rest on a general benchmark.
  - 66 of 94 answers passed the first check; 28 were revised; 7 still failed after two revisions and kept only their verified sentences or declined.
  - $0.0008 an answer at list prices, about 70% on top of the doc agent's $0.0011.
- **Problems and fixes:**
  - **The grader in the loop:** the obvious checker was the faithfulness judge's own model; the checker is a third model, so the evaluation stays independent.
  - **A revision that ends in a refusal** was first reported as unchecked; the response now marks it checked and refused.
  - **Two days of quota:** the 94 checks and 28 revisions ran across two days of free-tier caps, in the same loop as the other Phase 5 runs.
- **Decisions:** [ADR-0019](decisions/0019-validator-loop.md).
- **Next:** memory (step 5.5), self-consistency (step 5.4) and the end-to-end evaluation (step 5.6).

### 2026-10-25 · Phase 5 · Hybrid answers, version 2

- **Goal:** the graph's hybrid node, with the changes the prototype's report asked for (step 5.1).
- **Done:**
  - `copilot.answer.hybrid_v2.HybridAgentV2`: questions about one company and at most two consecutive years, the later with a 10-K in the corpus, go to the doc agent alone; any other question is split by a planner call into a figures question for the data agent and a reasons question for the doc agent's retrieval; the answer gives what the sources support and names the rest in `missing`; something missing triggers a second search across the company's filings and a second answer.
  - The graph's hybrid node uses it, and records the path, the plan and whether it retried; `poe ask` shows what is missing.
  - `fill` keeps computed figures readable: it drops a placeholder whose result the sentence already states, writes results from the facts database's dollars in millions or billions, and shows a fall without a minus sign after words that say so.
  - The [version 2 report](eval/hybrid-v2.md), and version 2 in the [hybrid answers guide](concepts/hybrid-answers.md#version-2).
- **Commands:** `uv run poe run-hybrid --agent hybrid-v2 --run hybrid-v2`, `uv run poe compare-runs eval/results/hybrid/hybrid-v1/dev eval/results/hybrid/hybrid-v2/dev --metric all_figures`.
- **Results:**
  - Every one of the 13 hybrid-set questions answered with every expected figure, against 10 for the prototype and for the doc agent alone; the three five-year questions took the split path, the other ten went to the doc agent alone.
  - Faithful 7 of 13 (0.54), between the prototype's 8 and the doc agent's 6; in two of the three split-path answers, sentences of the explanation were judged unsupported.
  - $0.0034 a question, 30% below the prototype's $0.0048: $0.0025 on the doc path and $0.0062 on the split path.
  - On 13 questions none of the differences is significant (three questions all one way: p = 0.25).
- **Problems and fixes:**
  - **A change written twice, in raw units:** the model still wrote some computed changes itself and added the placeholder ("$122 million ... 122,000,000"); `fill` now drops the repeat.
  - **Units the calculator can't see:** a first fix wrote every large result in billions and turned a decline of $7,737,590 thousand into "7.738 million"; results are now compacted only when every operand comes from the facts database. The run was repeated from the cached calls: four answers read differently, and no check changed.
  - **A day of spent quotas:** the run's three split-path questions waited a day for the strong model's quota; refused calls retried after pauses, which shows in the longest model time, 242 s.
- **Decisions:** adopt version 2 as the hybrid node ([report](eval/hybrid-v2.md)); no ADR, since it carries out the prototype report's plan.
- **Next:** the validator (step 5.3), then memory (step 5.5).

### 2026-10-24 · Phase 5 · The routing test split

- **Goal:** the one honest check of the routers, on seeds that no prompt example or design choice had seen, as ADR-0017 set out.
- **Done:** opened the routing set's held-out test split once, with prompt `r1` and the semantic router's configuration frozen, and ran the LLM router, the semantic fallback and both floors on its 60 questions.
- **Commands:** `uv run poe run-router --router llm --role strong --run llm-gpt-oss-120b --split test --allow-test`, the same for `--router semantic --mask entities --method centroid --run semantic-masked-centroid`, `uv run poe eval-routing --baseline keyword --split test --allow-test` (and `majority`), and `uv run poe compare-family` against the keyword rules.
- **Results:**
  - The LLM router on gpt-oss-120b: 60 of 60 (exact 0.940 to 1.000), $0.00018 a question.
  - The masked-centroid semantic router: 0.800 (0.700 to 0.900), against 0.739 on dev, so the choices made on dev held. On paraphrases it beats the keyword rules by +0.275 (+0.100 to +0.450), p = 0.008.
  - The keyword rules 0.650 and the majority route 0.250.
- **Problems and fixes:**
  - **The fallback's confusions moved:** five of nine `decline` requests (a share price next year, non-public earnings details) went to `data`, where on dev they went to small talk. ADR-0017's consequences now say so.
  - **Latency on the free tier:** the run waited out spent quotas, so its 95th-percentile latency (48 s) measures the pauses, not the router.
- **Decisions:** [ADR-0017](decisions/0017-routing.md) stands, with the test split in its evidence.
- **Next:** the remaining Phase 5 runs: hybrid answers v2, the validator, self-consistency and the end-to-end evaluation.

### 2026-10-24 · Phase 5 · The copilot as a graph

- **Goal:** one copilot that routes each question and runs every step in view (step 5.1).
- **Done:**
  - `copilot.agents.graph`: a LangGraph state graph: rewrite, understand, route, then the doc agent, the data agent, the hybrid, a brief note, small talk or a decline, then synthesise, validate and respond. The state holds plain JSON; the first node clears what the previous turn left; the history only grows.
  - `copilot.agents.runner`: `Copilot.stream` turns the graph's stream (`tasks` and `custom` parts, `version="v2"`) into events, a start and a timed end for every node, the nodes' own events and the response, and `TraceWriter` keeps them as JSON lines in `data/traces/`.
  - `copilot.agents.build`: the real agents and the router of ADR-0017, with every component's model calls cached; batch runs are paced and stop on a spent quota, interactive ones make one attempt and fall back. `postgres_checkpointer` keeps conversations in the Compose Postgres.
  - `poe ask` runs one question through the graph and prints each step; `--thread` and `--postgres` continue a conversation.
  - [ADR-0018](decisions/0018-graph-design.md) and the [LangGraph orchestration guide](concepts/langgraph-orchestration.md).
- **Commands:** `uv run poe ask "..." --verbose`, `uv run poe ask "..." --thread smoke-pg --postgres`, `uv run poe check`, and the Postgres test with `pytest -m integration`.
- **Results:**
  - 19 tests of the graph with fakes, and one against Postgres: a conversation started by one `Copilot` continues in another.
  - A live question from the hybrid set, on a day the strong model's quota was spent: the router fell back to its semantic half, which chose `hybrid`, and the hybrid agent answered from its cached calls with the query and three pages cited. The trace held a start and an end for each of its 7 nodes. The route took 12.8 s, the gateway retrying the refused call; the other nodes together under a second.
  - A two-turn conversation in Postgres: "Hi! Which companies do you cover?" went to small talk, which listed the 40 companies, and "Should I buy Nike stock right now?" was declined, asked from a new process as the thread's second turn.
- **Problems and fixes:**
  - **A checkpointer remembers too much:** a prototype showed one turn's answer in the next turn's state, so the first node resets the per-turn keys.
  - **The trace needs a checkpointer:** `get_state` and the `tasks` stream mode need one, so `Copilot` always has one.
  - **Event fields that clash:** the synthesise node's `kind` collided with the trace helper's keyword, now positional-only.
  - **Pacing is for batches:** interactive clients count tokens without pausing and make one attempt, so a spent quota means a quick fallback, not minutes of waiting.
- **Decisions:** [ADR-0018](decisions/0018-graph-design.md).
- **Next:** hybrid answers v2 (step 5.1's hybrid node), then the validator (step 5.3).

### 2026-10-24 · Phase 5 · Routers

- **Goal:** choose the router that sends each question to the right part of the copilot, by measurement (step 5.2).
- **Done:**
  - `copilot.agents.router`:
    - a **semantic router** over the routing set's dev questions (bge-small; a vote of the k nearest or the nearest route centroid; company names and years masked);
    - an **LLM router** (prompt r1: the route definitions, the labelling rules, the database's measures and 13 examples written for it; JSON out);
    - a **cascade** of the two, used as the LLM router with the semantic router as its fallback.
  - `poe run-router`, resumable, with latency, tokens and cost per question and a confusion matrix for every routing run, baselines included.
  - The gateway gained a third model role, `small` (gpt-oss-20b), and `role_models()` replaced seven hand-built maps from roles to models.
  - A [report](eval/routing.md), [ADR-0017](decisions/0017-routing.md) and the [semantic routing guide](concepts/semantic-routing.md); the runbook, the glossary and the gateway guide updated.
  - The plan's leftovers from AWS (the open decision on HTTPS, a prerequisite and a risk) and duplicate rows in the decision index and the glossary.
- **Commands:** `uv run poe run-router --router semantic --mask entities --method centroid --run semantic-masked-centroid` and six other semantic variants; `uv run poe run-router --router llm --run llm-…` on three models; `uv run poe compare-family ...`; `uv run poe check`.
- **Results** (routing dev, 138 questions):
  - **LLM router:** gpt-oss-120b 1.000 (exact 95% interval 0.974 to 1.000), $0.00019 and 0.51 s a question; gpt-oss-20b 0.964 (0.928 to 0.993), $0.00010; Qwen3.8 27B 1.000 too, at $0.00080 and 0.33 s. All three were right on every `doc`, `data` and `hybrid` question.
  - **Semantic router**, with each question's seed group left out of its examples: 0.391 as first designed (a vote of five), 0.739 (0.667 to 0.812) with masking and centroids, 8 ms a question.
  - **Floors:** the keyword rules 0.623 (0.957 on the seeds they were written on, 0.457 on paraphrases); on paraphrases the masked-centroid router beats them by +0.283, p = 0.0001.
- **Problems and fixes:**
  - **A paraphrase in the index is a leak.** A question's own paraphrases are at a median similarity of 0.936 to it, so the semantic router is evaluated with each seed group left out.
  - **Topic beats intent.** The first semantic design's neighbours shared the question's company or metric, not its route; masking and centroids fixed most of it, chosen on dev.
  - **Prompt examples near test questions.** Two first drafts came within 0.91 of held-out test questions by embedding similarity, checked by number only, and were replaced.
  - **The fast model is the costly one.** Qwen3.8 27B costs $0.80 and $4.00 per million tokens in and out, against gpt-oss-20b's $0.075 and $0.30, which is why the gateway gained a `small` role. The full runs then showed gpt-oss-20b misrouting the questions about what the copilot covers and won't do, so the router moved to `strong`, and `small` serves the cheapest calls.
  - **Daily caps.** Qwen and gpt-oss-120b ran out of their daily quotas mid-run; one loop took turns between the runs and resumed each as its quota came back. A run killed while appending now skips the half-written line.
- **Decisions:** [ADR-0017](decisions/0017-routing.md): route with the LLM router on gpt-oss-120b, and keep the semantic router as its fallback.
- **Next:** the graph (step 5.1), with this router in front.

### 2026-10-23 · Planning · Google Cloud for the deployment

- **Goal:** move the planned deployment (Phase 8) from AWS to Google Cloud while no cloud code exists, so the change costs nothing.
- **Done:**
  - [ADR-0016](decisions/0016-deploy-on-google-cloud.md), superseding [ADR-0003](decisions/0003-aws-demo-windows.md).
  - Rewrote Phase 8's steps and the definition of done, and updated the prerequisites, technical choices, risks and change log.
  - Updated the README, the glossary, the planned guides and the project page (the platform, the deployment diagram, the guardrails, the risks, the roadmap and the stack).
- **Commands:** `uv run poe check`.
- **Results:** no code changes beyond one docstring.
- **Problems and fixes:** none.
- **Decisions:**
  - **Services:** Cloud Run services that scale to zero, and a Pub/Sub-fed worker for ingestion.
  - **Data:** Cloud SQL for PostgreSQL, started only for demos; Firestore for quotas.
  - **Delivery and secrets:** Artifact Registry, Secret Manager, deploys through Workload Identity Federation, and Terraform; region `asia-south1`.
  - **Credit:** the free-trial credit lasts 90 days, so Phase 8's cost measurements should run inside it.
- **Next:** Phase 5, orchestration with LangGraph.

### 2026-10-23 · Phase 4 · Phase 4 complete

- **Goal:** open the SQL set's held-out test split, the milestone run, confirm Phase 4's exit criterion and publish it.
- **Done:**
  - **The milestone run:** the data agent as it stood after value linking (step 4.2), unchanged since, on the SQL set's 14 test questions.
  - **The exit criterion is met:** execution accuracy is reported with intervals (0.61 to 1.00 on dev, 1.00 on test), and the [hybrid prototype](eval/hybrid-prototype.md) answers 10 of its 13 questions with every expected figure.
  - Updated the plan (status tracker), the README, the guides, the SQL set's data card and the project page (status, the data agent, the worked example, the evaluation table, the guardrails, the roadmap).
- **Commands:** `uv run poe run-sql-agent --split test --allow-test --run sql-agent-v2`, `uv run poe check`.
- **Results:**
  - **Held-out test split:** 14 of 14 right, answering the 11 it could and declining the 3 it couldn't; exact 95% interval 0.77 to 1.00, with one repair and 1.9 s of model time at the median. The definitions written on dev held up on the test split's two ratio questions, which they weren't shaped on.
  - **Phase 4 in sum:**
    - execution accuracy 0.61, then 1.00 with value linking on dev, and 1.00 on test;
    - 32 of FinanceBench's 33 dev figure questions right, where the doc agent gets 29;
    - a typed answer for the orchestrator;
    - a hybrid-answer prototype whose failures set Phase 5's agenda.
- **Problems and fixes:** the free tier's rolling daily caps spread the last runs over about 15 hours. The runs resume, and a loop restarted them every 20 minutes until each finished.
- **Decisions:** [ADR-0015](decisions/0015-reuse-text2sql-analyst.md) holds the design: text2sql-analyst, improved upstream and pinned. The test split is now spent, so further SQL-set results are on dev only.
- **Next:** Phase 5, orchestration with LangGraph:
  - a router, measured on the routing set;
  - a validator loop;
  - hybrid answers rebuilt with partial answers, the retry and a planner that splits each question between the agents.

### 2026-10-23 · Phase 4 · Hybrid answers

- **Goal:** one answer that takes its figures from the data agent and its reasons from the filings, compared with the doc agent alone (step 4.6).
- **Done:**
  - `copilot.answer.hybrid.HybridAgent`. The data agent answers the question with a hint that other sources answer the reasons, and its query result, the SQL with the rows, becomes source [1]. The doc agent's retrieval supplies the pages from [2]. One gpt-oss-120b answer follows the doc agent's rules plus two: figures from the database, and a page that states a figure differently pointed out.
  - A [hybrid question set](data/hybrid-set.md): 13 questions on dev companies, with expected figures as formulas over annual values, and the figure check in `copilot.eval.hybrid`.
  - `poe run-hybrid`: either agent on the set, resumably, then the faithfulness judge, the figure and citation checks, and costs. Answers are committed without page text.
  - A [report](eval/hybrid-prototype.md) and a [guide](concepts/hybrid-answers.md).
- **Commands:** `uv run poe run-hybrid --agent hybrid --run hybrid-v1`, `uv run poe run-hybrid --agent doc --run doc-agent-v4`, `uv run poe compare-runs eval/results/hybrid/doc-agent-v4/dev eval/results/hybrid/hybrid-v1/dev --metric all_figures`, `uv run poe check`.
- **Results** (13 questions):
  - Each agent answered 10 with every expected figure and explained 9. Every sentence was supported by its citations in 8 of the hybrid's answers and 6 of the doc agent's (p = 0.63).
  - Only the hybrid answered the five-year 3M question, whose 2019 figure is in no filing in the corpus. Only the doc agent answered Boeing's segment question, through its retry.
  - The hybrid refused three questions whose figures it had, because no retrieved page explained them.
  - $0.0048 a question, against the doc agent's $0.0030.
- **Problems and fixes:**
  - **The narrative half made the data agent decline.** It declined the first smoke run's 3M question as "qualitative commentary". A firmer hint fixed that one; Adobe's still declined in the full run.
  - **Questions that didn't test the point.** The first ten asked about two years that one filing states, and the doc agent gave every figure too. Three five-year questions, whose middle years aren't in the corpus's filings, were added after that run, and the data card says so.
  - **Two run loops at once.** A run loop that had been stopped kept running, so two loops took turns until one was killed. No file was damaged, and a loop now starts only after a check that none is running.
- **Decisions:** neither agent changes now. Thirteen questions written by the same project are design evidence for Phase 5, not a basis for tuning: partial answers, the retry, a planner that splits questions, routing by need, and computed figures written once.
- **Next:** close Phase 4: the SQL set's held-out test split, the plan, the README and the project page.

### 2026-10-23 · Phase 4 · The data agent on FinanceBench

- **Goal:** measure the data agent on FinanceBench's figure questions against the doc agent, with the same questions and the same judges (step 4.5).
- **Done:**
  - `poe answer-with-data`: the data agent answers FinanceBench dev questions resumably, in the shape the judge reads, with its SQL, rows, tokens by model and cost kept locally. The written answer comes from gpt-oss-120b, the doc agent's answer model.
  - `build_pipeline(analysis_model=...)`, `PacedLLM.tokens_by_model`, and `token_cost` in the gateway, for costs across models.
  - `poe compare-runs --where question_type=metrics-generated` compares runs on the questions they share, and a yes-or-no metric now gets a count of who gets each question.
  - A [report](eval/data-agent-financebench.md), with a hand review of the one answer that wasn't correct.
- **Commands:** `uv run poe answer-with-data`, `uv run poe judge-answers --run data-agent-v1` and the same with the gpt-oss-20b judge, `uv run poe compare-runs ... --where question_type=metrics-generated`, `uv run poe check`.
- **Results** (33 dev metrics questions):
  - 32 correct by both judges (0.97; exact 95% interval 0.84 to 1.00), against the doc agent's 29 (0.88).
  - Right wherever the doc agent is. It also answers two calculations across years that the doc agent refused, and a return on assets the doc agent wrote as a percentage. Difference +0.09 (0.00 to +0.21), p = 0.25.
  - Every query used `annual_values` and `companies`, followed the question's own definitions, and rounded in SQL as the question asked; one needed a repair.
  - About 4,900 tokens, 2.8 s of model time and $0.0025 a question, against the doc agent's $0.0010 on the same questions. The table-selection call on Qwen3.8 27B is two thirds of the cost.
- **Problems and fixes:**
  - **Runs over different questions.** `compare_runs` rightly refused to pair a 33-question run with a 100-question one. `--where` now keeps the shared questions explicitly, rather than intersecting them silently.
  - **The judge and the writer.** The data agent normally writes its answer with Qwen, the default judge's own model. This run used gpt-oss-120b instead, as the doc agent does, which keeps the judge apart from the writer and leaves the source of the numbers as the only difference.
  - **A rounding miss.** The one wrong answer gives the reported $389 million as $0.39 billion; the reference rounds it to one decimal and writes $0.40.
- **Decisions:** figure questions go to the data agent in Phase 5; the agent itself stays as it is.
- **Next:** hybrid answers that combine the data agent's numbers with the doc agent's narrative (step 4.6), then the SQL test split and the close of Phase 4.

### 2026-10-23 · Phase 4 · The data agent as a tool

- **Goal:** one typed result from the data agent that the orchestrator, the API and the MCP server can check, store and send (step 4.4).
- **Done:**
  - `copilot.sql.tool.DataAgent.ask(question)` returns a `DataAnswer`, a pydantic model of this project's own:
    - the status (`ok`, `unanswerable` or `error`) and the written answer, with insights and caveats;
    - the SQL, the columns and rows, exact statistics and a chart spec;
    - the tables used, the hints, the number of attempts and the timings.
  - Failures come back as a status, never as an exception, and the answer survives a JSON round trip.
  - `column_statistics`: the count, total, mean, minimum and maximum of each measure column, and the label of the row where each extreme falls.
  - `poe ask-data "..."` prints one answer, or the whole model with `--json`.
  - A [Text-to-SQL agent guide](concepts/text-to-sql-agent.md) on the pipeline end to end.
- **Commands:** `uv run poe ask-data "How did 3M's capital expenditure change from fiscal 2018 to fiscal 2022?"`, `uv run poe check`.
- **Results:** that question gets one query over five rows: $1.577 billion to $1.749 billion (+10.9%), with the 2020 low and the 2022 peak named and a line chart suggested.
- **Problems and fixes:**
  - **Years counted as measures.** The first statistics added up the fiscal years (a "total" of 10,100) and had no column left to label the extremes. The tool now uses text2sql-analyst's rules for measure, identifier and period columns, with `cik` as an identifier too, so a year labels the rows.
  - **Types for pandas.** Those rules take a DataFrame, so pandas is now a direct dependency, and `pandas-stubs` keeps mypy strict.
- **Decisions:** callers depend on `DataAnswer`, not on text2sql-analyst's classes, so a library upgrade touches one function (`to_answer`).
- **Next:** the data agent on FinanceBench's metrics questions, judged as the doc agent's answers were and compared question by question (step 4.5).

### 2026-10-23 · Phase 4 · Value linking

- **Goal:** give the data agent the database values its questions refer to, which the schema doesn't show (steps 4.2 and 4.3).
- **Done:**
  - **Upstream:** text2sql-analyst [PR #2](https://github.com/VinayakMokashi/text2sql-analyst/pull/2) (version 0.3.0) adds `text2sql.linking`:
    - `ColumnCatalogue`, a short column's values with labels;
    - `ValueMatcher`, values a question mentions, by name or alias;
    - `StaticLinker`, and `Pipeline(..., linker=...)`, which adds a linker's hints to every question.
  - Pinned at bfaafdf.
  - `copilot.sql.linking.FactsLinker`. The hints:
    - each company the question names (the query-understanding matcher), with its database name, CIK and fiscal-year coverage;
    - every company in the database;
    - the metric catalogue;
    - definitions of combined measures;
    - notes on fiscal years and on naming companies.
  - `poe run-sql-agent --no-linking` reproduces the baseline; a [value linking guide](concepts/value-linking.md).
- **Commands:** `uv add "text2sql-analyst @ git+...@bfaafdf"`, `uv run poe run-sql-agent`, `uv run poe compare-runs eval/results/sql/sql-agent-v1/dev eval/results/sql/sql-agent-v2/dev --metric accuracy`, `uv run poe check`.
- **Results** (28 dev questions):
  - All 28 right: accuracy 1.000, exact 95% interval 0.88 to 1.00, against 0.607 without linking (+0.393, p = 0.001).
  - All seven unanswerable questions were declined at table selection, citing the hints.
  - About 3,300 tokens a question, 1,000 more than without linking.
- **Problems and fixes:**
  - **A perfect score's interval.** The bootstrap interval collapses to a point when every answer is right, so the exact binomial interval is reported instead.
  - **Tuned on dev.** The definitions of combined measures were written after reading the baseline's errors, and the dev set asks for those measures. The fair checks are FinanceBench's metrics questions (step 4.5) and the SQL test split at the end of Phase 4.
- **Decisions:** value linking goes in as hints, not as changes to text2sql-analyst's prompts. The parts any database can use went upstream; companies, coverage and definitions stay here.
- **Next:** the data agent as a typed tool (step 4.4), then FinanceBench's metrics questions against the doc agent (step 4.5).

### 2026-10-23 · Phase 4 · Data agent baseline

- **Goal:** answer questions about reported figures with SQL over the facts database by reusing text2sql-analyst, and measure where it starts (step 4.1).
- **Done:**
  - **Upstream first.** text2sql-analyst [PR #1](https://github.com/VinayakMokashi/text2sql-analyst/pull/1), version 0.2.0:
    - ChromaDB, Streamlit and Altair became optional extras, and ChromaDB loads only when a collection is opened;
    - a `SchemaRetriever` protocol and an `AllTablesRetriever`;
    - `hints` passed to the selection and SQL prompts.
  - Pinned at commit 2b89c30.
  - `copilot.sql.adapter.GatewayLLM`: text2sql-analyst's model interface on the cached, paced gateway, with "sql" mapped to the strong model and "helper" to the fast one.
  - `copilot.sql.agent.build_pipeline`: the pipeline over the facts database, every table offered with the hand-written descriptions.
  - `poe run-sql-agent`: answers the SQL set resumably and scores it as `poe eval-sql` does, with each question's status, tables, attempts, tokens and model time.
  - [ADR-0015](decisions/0015-reuse-text2sql-analyst.md).
- **Commands:** `uv add "text2sql-analyst @ git+...@2b89c30"`, `uv run poe run-sql-agent`, `uv run poe compare-runs eval/results/sql/decline-all/dev eval/results/sql/sql-agent-v1/dev --metric accuracy`, `uv run poe check`.
- **Results** (28 dev questions):
  - Execution accuracy 0.607 (0.43 to 0.79): 12 of 21 answerable questions, 5 of 7 unanswerable.
  - +0.357 over declining everything (p = 0.015).
  - No repairs or failed queries; about 2,300 tokens a question.
- **Problems and fixes:**
  - **A dependency built as an app.** Pinning text2sql-analyst as it was would have installed Streamlit, Altair and a second vector database to index seven tables. Making them optional upstream kept the addition to eight small packages.
  - **The agent doesn't know the metric names.** Seven of nine wrong answers guessed names that don't exist (`netProfitMargin`, `cashAndCashEquivalents`), because table selection never chose the `metrics` table that lists them. The two wrong declines queried a company and a year the database doesn't hold. Both are value linking, which is next.
- **Decisions:** [ADR-0015](decisions/0015-reuse-text2sql-analyst.md).
- **Next:** value linking and fiscal-calendar handling (steps 4.2 and 4.3).

### 2026-10-23 · Phase 3 · Phase 3 complete

- **Goal:** confirm Phase 3's exit criterion and publish the milestone.
- **Done:**
  - **The exit criterion is met:** the [dev evaluation](eval/doc-agent-dev.md) reports correctness, faithfulness, citation precision, refusals, latency and cost with 95% intervals, and the top error categories.
  - Updated the plan (steps, status tracker), the README and the project page (status, the doc agent, the retrieval diagram, the evaluation table, the roadmap).
- **Commands:** `uv run poe check`.
- **Results:** the doc agent answers 65% of dev questions correctly (0.56 to 0.74), 88% of figure questions, at about $0.0011 a question.
- **Problems and fixes:** none new.
- **Decisions:** v4 is the Phase 3 doc agent ([report](eval/doc-agent-dev.md)); ADRs 0012 to 0014 hold the design.
- **Next:** Phase 4, the data agent: Text-to-SQL over the XBRL facts database, which the error analysis also points to for ratio questions whose definitions the filings don't print.

### 2026-10-23 · Phase 3 · Dev evaluation

- **Goal:** measure the doc agent on the 100 dev questions: correctness, faithfulness, citation precision, refusals, latency and cost, and find where the wrong answers come from (step 3.7).
- **Done:**
  - `copilot.eval.faithfulness` and `poe check-faithfulness`: one judge call per answer checks each cited sentence against its cited pages and the calculations behind it, giving faithfulness and citation precision.
  - `copilot.eval.errors` and `poe analyse-errors`: one category per answer that isn't correct, with model latency and cost at list prices; a reading of all 29 incorrect answers against their references and sources.
  - A post-processing fix (v4): calculations may use earlier results, and placeholders may scale a result or give its decimals.
  - The [dev evaluation report](eval/doc-agent-dev.md).
- **Commands:** `uv run poe answer-questions --run doc-agent-v4-full` (all from the cache), `uv run poe judge-answers`, `uv run poe check-faithfulness` and `uv run poe analyse-errors` on both runs, `uv run poe compare-runs ... --metric correct`, `uv run poe check`.
- **Results:**
  - Correct 0.65 (0.56 to 0.74) by the Qwen judge and 0.63 by gpt-oss-20b; incorrect 0.29; refused 0.06. Metrics-generated questions 0.88, domain-relevant 0.59, novel-generated 0.48.
  - Faithful 0.63 (Qwen) and 0.68 (gpt-oss-20b) of answered questions; citation precision 0.93 and 0.84; an evidence page cited for 0.64 of questions.
  - The retry ran for 16 questions: 6 became correct answers, 4 wrong ones, and 6 stayed refused.
  - Model latency 2.34 s at p50 and 5.52 s at p95; 5,403 tokens and about $0.0011 a question at list prices.
  - v4 against v3: correctness unchanged (p = 1.0 with both judges); failed calculations 11 to 0, unfilled placeholders 3 to 0.
  - Of the 29 incorrect answers, 18 had the evidence page in context: 6 used another definition of the measure, 6 were incomplete, 6 misread a figure, 4 took the wrong line item, 3 the wrong period, 2 reached a different judgement, and 2 are arguably correct.
- **Problems and fixes:**
  - **Calculations that build on each other.** The model wrote `c1 / 4756` with `c1` an earlier result, and the calculator rejected the name 11 times; calculations now run in order with earlier results substituted.
  - **Python habits in placeholders.** `{c1*100}` and `{c1*100:.1f}` left raw placeholders in three answers; placeholders now take one operation and a number of decimals. Because only the post-processing changed, the whole run was rebuilt from the model-call cache with no new calls.
  - **Faithfulness depends on the judge.** The two models agree on 79 of 94 answers (84%) about faithfulness, less than on correctness, so the report gives both.
- **Decisions:** adopt v4; the next levers are definitions, completeness and the choice of filing, then the judge's precision rule ([report](eval/doc-agent-dev.md)).
- **Next:** close Phase 3.

### 2026-10-23 · Phase 3 · Answer judge

- **Goal:** grade answers against FinanceBench's reference answers automatically, and check the grader before trusting it (step 3.6).
- **Done:**
  - `copilot.eval.judge`: a rubric-bound judge on the fast model (Qwen), JSON verdicts with a reason, refusals without a call, and `closest_figures`, which pairs each reference figure with the answer's closest one and gives the judge the distance.
  - `copilot.eval.labels` and `poe label-sample`: a stratified, fixed-seed sample of 44 dev questions drawn before any answer was judged, answered first (`poe answer-questions --first`), and shown on a private labelling page exactly as the judge sees them.
  - `copilot.eval.stats.cohens_kappa` and `kappa_interval`; `poe judge-answers` and `poe judge-agreement`.
  - `copilot.llm.parsing.json_object`, shared by the answer step and the judge; the model-call cache now skips lines it can't read.
  - [ADR-0014](decisions/0014-answer-judge.md), an [LLM-as-judge guide](concepts/llm-as-judge.md) and a [data card](data/answer-labels.md) for the labels.
- **Commands:** `uv run poe answer-questions --run doc-agent-v3-full --first eval/labels/answer-correctness-sample.json` (about three days on the free tier), `uv run poe judge-answers --run doc-agent-v3-full` (and with `FRC_LLM_FAST_MODEL=groq/openai/gpt-oss-20b`), `uv run poe label-sample --run doc-agent-v3-full`, `uv run poe judge-agreement --run doc-agent-v3-full --judge qwen3.8-27b-p2 --judge gpt-oss-20b-p2`, `uv run poe check`.
- **Results:**
  - Against 41 reference labels: the Qwen judge agrees on all 41 (kappa 1.00); gpt-oss-20b on 38 (kappa 0.84, 0.63 to 1.00), stricter on the three it differs on.
  - The two judges agree on 87 of the 94 answered dev questions (kappa 0.83).
  - About 660 tokens a verdict; no invalid verdicts.
- **Problems and fixes:**
  - **The judge couldn't do the arithmetic it checks.** The first rubric left "within 1%" to the model, which called 8.738 and 8.70 more than 1% apart; code now computes the distances.
  - **The rubric was silent on the hard case**, a right conclusion resting on a wrong figure, and the first judge decided it both ways. The rubric now says a figure given for something the reference quantifies must match too.
  - **Labels from a model.** The plan called for about 40 answers labelled by hand. The labels came from a Claude model given the same page instead, and matched the default judge on every answer. The docs call the judge checked against a stronger model, not validated against a person, and a person check of about 20 answers stays open.
  - **Daily caps.** The 100-question dev run needed three days of the strong model's rolling daily quota; a loop re-ran the resumable job every 20 minutes and answered the labelling sample first.
- **Decisions:** [ADR-0014](decisions/0014-answer-judge.md).
- **Next:** the dev evaluation (step 3.7): correctness, faithfulness, citation precision, refusals, latency and cost, with an error analysis.

### 2026-10-19 · Phase 3 · Grounded answers

- **Goal:** turn the retrieved pages into cited answers, with the arithmetic done by a calculator and an honest refusal when the evidence isn't there (steps 3.3 to 3.5).
- **Done:**
  - `copilot.answer.context`: numbered sources labelled with company, form, period and PDF page, packed in rank order to a token budget; `poe eval-context` measures how often an evidence page makes the context.
  - `copilot.answer.calculator`: model-written expressions cleaned of separators, currency signs and percentages, and evaluated with the facts formula parser.
  - `copilot.answer.generate`: the answer prompt, one JSON-mode call to the strong model, lenient parsing with schema validation, placeholders filled by the calculator, and citation checks.
  - `copilot.answer.agent`: the doc agent (retrieve, build the context, answer) with one retry that searches for what a refusal named as missing, across the company's filings.
  - `poe answer-questions`: answers dev questions resumably, keeps the full answers in `data/processed/answers/` and writes ids and measures to `eval/results/answers/`.
  - `PacedLLM` now pauses in proportion to the tokens each call used (`FRC_LLM_TOKENS_PER_MINUTE`).
  - [ADR-0013](decisions/0013-answer-format.md) and guides on [grounded generation](concepts/grounded-generation.md) and [corrective RAG](concepts/corrective-rag.md).
- **Commands:** `uv run poe eval-context`, `uv run poe compare-family ... --metric context_hit`, `uv run poe answer-questions --run doc-agent-v1 --limit 10` (and `v2`, `v3` after each fix below), `uv run poe check`.
- **Results:**
  - Context (100 dev questions): an evidence page is among the sources for 0.68 of questions at 3,000 tokens (8.2 sources on average). 1,500 tokens (0.52) and completing split pages (0.61) are significantly worse; 4,500 tokens (0.73) is not significantly better.
  - First smoke run (10 questions, prompt 1): 8 answered, no invalid citations and no failed calculations, but 3 of the 8 answers had no recognised citation, and the retry never ran.
  - Second smoke run (prompt 2, a retry aimed at what is missing): 9 answered, 2 retried, 1 uncited; an evidence page in the context for 7 and among the cited sources for 5 (2 in the first run).
  - Third smoke run (a 4,500-token context for the retry): the same counts, but the retried ratio question now uses the right revenue figure and matches the reference answer. About 5,700 tokens a question with retries.
- **Problems and fixes:**
  - **Citations in another bracket style.** gpt-oss-120b sometimes cites as 【1】, a habit from its browsing-tool training, and twice it cited nothing. The parser now reads both styles, and the second prompt says that an answer without citations is not accepted.
  - **A retry that never ran.** The first version retried only when the company had more filings than the resolver chose. Both refusals were about Activision Blizzard, which has one filing in the corpus, and its 10-K does hold both figures. The retry now searches for what the refusal named as missing, weighted as much as all the other searches together.
  - **The retry's new pages pushed out old ones.** At 3,000 tokens the pages found for the gap displaced the income statement, so one retried answer computed its ratio from the wrong figure. Offline, with the same searches, a 4,500-token second context held both evidence pages; the retry now gets that budget.
  - **Tokens a minute.** At about 4,000 tokens an answer, a fixed three-second pause ran into Groq's limit of 8,000 a minute on nearly every call; the pause now scales with the tokens used, about 30 seconds an answer.
- **Decisions:** [ADR-0013](decisions/0013-answer-format.md): 3,000-token context, one JSON answer call with citations, the calculator for arithmetic, and one retry aimed at what is missing, with a 4,500-token context.
- **Next:** the LLM judge, checked against about 40 answers labelled by hand (step 3.6).

### 2026-10-19 · Phase 3 · Query rewriting

- **Goal:** search for what each question needs, not for how it was asked (step 3.2), and re-test hybrid search and reranking once the template text is gone.
- **Done:**
  - `copilot.llm.cache.CachedLLM`: a JSON Lines cache of model calls keyed by model, messages and parameters; `copilot.llm.pacing.PacedLLM`: pauses after uncached calls, retries rate limits, and adds up tokens and latency.
  - `copilot.retrieval.rewrite`: multi-query, HyDE and decomposition prompts, parsing, and `expand`/`aexpand` (the question first, then the rewrites; `aexpand` requests them in parallel). `Searcher.search(passage=True)` embeds a HyDE passage as a document.
  - `poe run-retrieval --rewrite` and `--rerank-query rewrite`; [ADR-0012](decisions/0012-query-understanding-and-rewriting.md) and a [query rewriting guide](concepts/query-rewriting.md).
- **Commands:** `uv run poe run-retrieval --collection fb_page_bge-small --mode dense --setting understood --rewrite all` (and each rewrite alone), the hybrid and reranker re-tests, `uv run poe compare-family`, `uv run poe check`.
- **Results** (100 dev questions, dense search over page chunks inside the resolved filings):
  - recall@10 / MRR@10: no rewriting 0.570 / 0.381; multi-query 0.682 / 0.454; HyDE 0.682 / 0.388; decomposition 0.662 / 0.415; all three 0.722 / 0.476. Every rewrite is significantly better on recall@10; all three is also significantly better on MRR (p = 0.018).
  - All three rewrites cost 62,700 tokens for 100 questions on the fast model, once; every rerun since came from the cache.
  - Re-tests on the rewrites: hybrid 0.697 / 0.436 and bge-reranker-base against a rewritten query 0.692 / 0.436, neither significantly different; the reranker against the original question 0.650 / 0.335, significantly worse on MRR.
- **Problems and fixes:**
  - **Quota.** A hundred uncached calls back to back would exceed 8,000 tokens a minute within seconds; `PacedLLM` spaces them three seconds apart and retries refusals.
  - **Benchmark text in results.** Rewrites paraphrase FinanceBench questions, so run files record how many searches of each kind ran, never their text.
- **Decisions:** [ADR-0012](decisions/0012-query-understanding-and-rewriting.md): resolve the filings, search all three rewrites in parallel, keep dense search alone.
- **Next:** context building, grounded answers with citations, and the calculator (steps 3.3 to 3.5).

### 2026-10-19 · Phase 3 · Query understanding

- **Goal:** turn the company, period and form a question mentions into the filings to search (step 3.1), to close the gap Phase 2 found between searching the right filing and searching all of them.
- **Done:**
  - `copilot.retrieval.query`: a company matcher (names, short names, tickers of three or more letters, common aliases such as "JnJ"; case-sensitive where a name is an ordinary word), period and form cues (fiscal years, quarters, dates, 10-K/10-Q/8-K/earnings), an outlook cue, and `resolve`, which turns the cues into a filing list or None.
  - `poe run-retrieval --setting understood`, recording which filings each question searched.
  - A [query understanding guide](concepts/query-understanding.md).
- **Commands:** `uv run poe run-retrieval --collection fb_page_bge-small --mode dense --setting understood`, `uv run poe compare-family`, `uv run poe check`.
- **Results** (100 dev questions, dense search over page chunks):
  - A company was found in 98 questions; the question's own filing was among the resolved ones in all 98, with 1.5 filings searched on average. The other two questions name no company.
  - recall@10 0.570 and MRR@10 0.381, against 0.415 and 0.230 across all filings (both p = 0.0001), and 0.630 and 0.423 within the question's own filing.
  - Hybrid search inside the resolved filings: recall@10 0.525, not significantly different from dense search.
- **Problems and fixes:**
  - **Next year's outlook lives in this year's filings.** "Is JnJ's adjusted EPS growth expected to accelerate in FY2023?" is answered by the fourth-quarter 2022 earnings release, so forward-looking questions also search the previous year.
  - **Dates and quarters.** An August 2023 date matched a second-quarter 10-Q and an 8-K for a second-quarter question until dates were mapped to their calendar quarter.
  - **Tickers that are words:** COST and PEP match only in upper case.
- **Decisions:** query understanding is rule-based: it costs no model call, it is deterministic, and it already includes the right filing for every question that names a company.
- **Next:** query rewriting (step 3.2), with every model call cached.

### 2026-10-18 · Phase 2 · Phase 2 complete

- **Goal:** confirm Phase 2's exit criterion and publish the milestone.
- **Done:**
  - **The exit criterion is met in its second form:** the [retrieval report](eval/retrieval-baseline.md) shows the chosen setup and explains why nothing beat dense-only search significantly on recall@10: FinanceBench's templated questions mislead BM25 and the MS MARCO rerankers. Page chunks, the chosen setup, rank the evidence significantly higher than 480-token windows on MRR@10.
  - Updated the plan (status tracker, technology table, change log), the README and the project page.
- **Commands:** `uv run poe check`.
- **Results:** on dev, dense search over page chunks: recall@10 0.630 and MRR@10 0.423 within the question's filing; recall@10 0.415 and MRR@10 0.230 across all 84 filings. Floors for Phase 3: an evidence page in the top 20 for 77% of questions within the filing and 52% across filings.
- **Problems and fixes:** none new.
- **Decisions:** [ADR-0011](decisions/0011-retrieval-baseline.md).
- **Next:** Phase 3, the doc agent: query understanding (company, period and form as filters, aimed at the corpus-wide gap), query rewriting, grounded answers with page citations, and an LLM judge checked against human labels.

### 2026-10-18 · Phase 2 · Synthetic pairs

- **Goal:** question-to-chunk pairs from training filings only, for fine-tuning the embedder in Phase 7 (step 2.6, second half).
- **Done:**
  - `copilot.training.pairs`: training filings (no test company, no dev-question filing), chunk sampling (at least 200 tokens and mostly letters, up to 6 per filing, a fixed seed per filing), the prompt, the checks, question normalisation, and an interleaved order across companies and filings.
  - `poe generate-pairs`: writes each kept pair or rejected reply as it arrives, resumes, alternates the fast and strong models, paces calls under the per-minute limit, and lets a role whose daily quota runs out drop out while the others continue; a committed manifest records counts and the file's checksum.
  - A [data card](data/synthetic-pairs.md).
- **Commands:** `uv run poe fetch-financebench --pdfs all`, `uv run poe parse-pdfs`, `uv run poe generate-pairs --per-doc 6`, `uv run poe generate-pairs --manifest-only`, `uv run poe check`.
- **Results:** 1,006 pairs from 195 filings of 27 companies; 132 of 1,138 replies rejected (128 copied, 4 format).
- **Problems and fixes:**
  - **Daily token caps.** Groq's free tier allows each model about 200,000 tokens a day, so the 1,138 calls took two days. A capped model now drops out of the rotation instead of ending the run, and `gpt-oss-20b` serves as the gateway's fallback.
  - **An alphabetical bias.** The first day's run worked through filings in order and stopped at the quota with nine companies (JPMorgan to Walmart) still uncovered. Chunks are now dealt round-robin across companies and filings, so every prefix of a run is balanced.
  - **Typography.** About half of one model's questions used curly quotes, non-breaking hyphens and narrow spaces; questions are normalised when parsed and when loaded.
- **Decisions:** training filings exclude dev-question filings as well as test companies, so a fine-tuned model can still be compared fairly on dev.
- **Next:** close Phase 2.

### 2026-10-18 · Phase 2 · Chunking comparison and the retrieval baseline

- **Goal:** compare chunking strategies and late chunking, re-check search modes and reranking on the winner, measure latency, and choose the baseline (steps 2.5 and the first half of 2.6).
- **Done:**
  - Indexed `page`, `tokens-256`, `semantic` and the jina-v2-small pair (chunk by chunk and late-chunked) for the 58 dev filings, and `page` for all 84 question filings; scored each with dense search.
  - Moved rank fusion into `copilot.retrieval.search` (`reciprocal_rank_fusion`): each ranking is put in a fixed order (score, then point id) and fused with `w / (k + rank)`.
  - Re-ran every BM25 and hybrid configuration on complete indexes, re-measured latency with the machine idle, and regenerated the [retrieval report](eval/retrieval-baseline.md) from the result files.
  - [ADR-0011](decisions/0011-retrieval-baseline.md); measured results added to the chunking, late-chunking, hybrid search, reranking and retrieval-metrics guides.
- **Commands:** `uv run poe index-corpus` for each strategy, `uv run poe run-retrieval`, `uv run poe compare-family`, `uv run poe check`.
- **Results** (100 dev questions, dense search within the question's filing):
  - Chunking, recall@10 / MRR@10: `tokens-480` 0.608 / 0.307, `page` 0.630 / **0.423**, `tokens-256` **0.640** / 0.377, `semantic` 0.610 / 0.364. No strategy differs significantly on recall@10; page chunks (p = 0.003) and `tokens-256` (p = 0.037) are significantly better on MRR@10 after Holm's adjustment.
  - Across all 84 filings, page chunks doubled MRR@10 (0.230 against 0.115, p = 0.0001).
  - Late chunking against the same model chunk by chunk: recall@10 0.613 against 0.593, not significant.
  - On page chunks, hybrid search and bge-reranker-base both lowered MRR@10 significantly (0.334 and 0.335 against 0.423).
  - Dense search answers in about 50 ms a question; rerankers add 2.6 to 8.7 seconds.
- **Problems and fixes:**
  - **Results that changed between runs.** The first BM25 and hybrid runs were made while the main index was still being built, and BM25's IDF depends on the whole collection (BM25 recall@10 0.425 then, 0.440 on the complete index). Separately, Qdrant's server-side fusion returned a different order on 35 of 40 identical calls: RRF makes tied scores common, and Qdrant ranks tied chunks in no fixed order. Fusing in our own code made every run repeatable; the report was corrected, and no conclusion changed.
  - **`--docs all` grew.** After all 368 PDFs were parsed for the synthetic pairs, `--docs all` meant every parsed filing, and an overnight page-index run put 228 training filings into the evaluation collection. The selection now lives in `copilot.ingest.jobs.select_documents` with a test (`all` is the 84 question filings, `corpus` every filing), and the extra 63,934 points were deleted.
  - **Docker stopped overnight.** Docker Desktop's engine was gone at 00:12 UTC, so the page index and two runs failed with "connection refused". Restarting it and the services brought every collection back intact, and the resumable index job finished the rest.
- **Decisions:** [ADR-0011](decisions/0011-retrieval-baseline.md): dense search over page chunks, without fusion, reranking or late chunking.
- **Next:** finish the synthetic pairs when the model quotas reset, then close Phase 2.

### 2026-10-17 · Phase 2 · Retrieval variants

- **Goal:** dense, BM25 and hybrid search, cross-encoder reranking and neighbouring chunks, each scored on FinanceBench dev evidence pages against plain dense search (step 2.4, and step 2.5 except chunking).
- **Done:**
  - `copilot.retrieval.search`: one Qdrant call per query, as dense, BM25 or hybrid (both rankings as prefetches fused with RRF, k = 60), with an optional document filter; neighbouring chunks; ranked chunks to ranked pages.
  - `copilot.retrieval.rerank`: FastEmbed cross-encoders (MiniLM-L6 and L12, jina-turbo, bge-base) over the top candidates.
  - `poe run-retrieval` (search, rerank, score and record latency in one step) and `poe compare-family` (paired tests against one baseline, Holm-adjusted across the variants tried).
  - A [retrieval report](eval/retrieval-baseline.md); guides on [hybrid search and RRF](concepts/hybrid-search-and-rrf.md), [reranking](concepts/reranking.md) and [retrieval metrics](concepts/retrieval-metrics.md); the evaluations runbook covers both commands.
- **Commands:** `uv run poe run-retrieval` for each configuration, `uv run poe compare-family`, `uv run poe check`.
- **Results** (100 dev questions, `tokens-480` chunks, recall@10):
  - Dense search within the question's filing: 0.608 (95% interval 0.52 to 0.70), hit@20 0.74, against the first-pages floor's 0.197.
  - BM25 0.425 and hybrid with 2 : 1 weights 0.470, both significantly worse; equal-weight hybrid 0.540, not significantly different.
  - Rerankers over dense search's top candidates: MiniLM-L6 0.510, jina-turbo 0.580. bge-base over the top 20 tied it (0.605): better on the human-written questions (0.773 against 0.697), worse on the templated domain questions (0.294 against 0.392). None of the three differs significantly after Holm's adjustment; MiniLM's loss (p = 0.033 alone) doesn't survive it.
  - Neighbouring chunks: 0.575, not significantly different.
  - Across all 84 filings: dense 0.345, BM25 0.155, hybrid 0.210; dense search loses 20 points of hit@20 when it must also find the filing.
- **Problems and fixes:**
  - **Templated questions.** Two thirds of FinanceBench's questions carry template instructions (how many decimal places to round to, what to say if a metric doesn't suit the company), whose words BM25 matches all over every filing. On the human-written questions BM25 beats dense search, 0.758 against 0.697. Rewriting questions before searching is Phase 3's job.
  - **RRF weights aren't multipliers.** Probing Qdrant 1.19 showed weighted fusion orders matching `1 / (k + rank / w)`: a larger weight flattens a list's contribution, so a dense weight of 2 made results worse. Recorded in the hybrid search guide.
  - **Rerankers trained on web search.** MS MARCO cross-encoders read short queries and paragraph-length passages; MiniLM also truncates question plus chunk at 512 tokens. jina-turbo, which reads everything, lost less.
- **Decisions:** provisional baseline: dense search, no fusion, no reranker. The chunking comparison and ADR-0011 follow.
- **Next:** the chunking and late-chunking comparisons as their indexes finish, latency on an idle machine, then the synthetic pairs.

### 2026-10-17 · Phase 2 · Embeddings and the Qdrant index

- **Goal:** index the chunks with dense and BM25 vectors in Qdrant, resumably, and add late chunking and the semantic chunker's embedder (step 2.3, and the rest of step 2.2).
- **Done:**
  - `copilot.ingest.embed`: bge-small-en-v1.5 through FastEmbed (bge's instruction on queries only) and `Qdrant/bm25` sparse vectors; hashing stand-ins for tests.
  - `copilot.ingest.index`: one collection per strategy and model, with a named cosine vector, a BM25 sparse vector with Qdrant's IDF modifier, payload indexes and explicit HNSW settings. Point ids come from chunk content hashes, and only missing ids are embedded, so every run resumes.
  - `copilot.ingest.jobs`: a local runner, one job per document, with a JSON Lines log; a failed document is recorded and the run moves on.
  - `copilot.ingest.late_chunking`: jina-embeddings-v2-small-en through ONNX Runtime, 2,048-token windows overlapping by 512, each token taking its vector from the window it sits nearer the middle of.
  - The semantic chunker now embeds sentences and paragraphs instead of PDF lines.
  - `poe index-corpus` (with an index card per collection) and `poe check-hnsw`; [ADR-0010](decisions/0010-vector-store-and-embeddings.md), guides on [late chunking](concepts/late-chunking.md) and [HNSW and Qdrant](concepts/hnsw-and-qdrant.md), and an indexing section in the [ingestion runbook](runbooks/ingesting-filings.md).
  - Parsing now reports and skips a PDF it can't open instead of stopping; all 368 FinanceBench PDFs were downloaded and 366 parsed (53,901 pages).
- **Commands:** `uv run poe index-corpus --strategy tokens-480 --model bge-small --docs all`, `uv run poe check-hnsw`, `uv run poe parse-pdfs`, embedding benchmarks, `uv run poe check`.
- **Results:**
  - Main index: 21,899 `tokens-480` chunks of the 84 question documents in about 79 minutes, sharing the CPU with other work for part of the run.
  - Embedding one chunk at a time ran at 9.0 chunks a second, against 5.5 in batches of 16; ONNX Runtime called directly gave the same speed and the same vectors.
  - HNSW check, with every search forced through the graph: recall@10 against exact search 0.883 at ef = 8, 0.986 at 32 and 0.999 at 128. Exact search over all 21,899 vectors answers in about 20 ms, so the main collection's exact search costs nothing measurable.
  - 252 tests pass offline; an integration test checks real late-chunked vectors.
- **Problems and fixes:**
  - **Batches were slower.** A batch is padded to its longest text and spills out of the CPU caches, so texts are embedded singly.
  - **A chunk can outgrow the window overlap.** Chunks are counted in bge tokens and jina's tokenizer splits differently, so a design that needed each chunk inside one window could fail. Tokens, not chunks, are now assigned to windows.
  - **PDF lines aren't sentences.** The semantic chunker had been embedding visual lines, mostly sentence fragments.
  - **Two truncated PDFs.** Intel's 8-Ks of 2023-02-10 and 2023-08-16 end mid-file in FinanceBench's own repository (no end-of-file marker), so neither pdfium nor pypdf can open them; parsing reports and skips them.
  - **"Indexed" didn't mean HNSW.** The collection counted every point as indexed, but those were the sparse vectors; the dense vectors sat in segments too small for an HNSW graph and were searched exactly.
  - **A graph that isn't used.** The first HNSW check scored a perfect 1.000 at every ef: segments under Qdrant's full-scan threshold are searched exactly even when they have a graph. Lowering that threshold and confirming the search path in Qdrant's telemetry fixed the measurement.
- **Decisions:** [ADR-0010](decisions/0010-vector-store-and-embeddings.md).
- **Next:** retrieval variants and their evaluation (steps 2.4 and 2.5), then synthetic pairs (2.6).

### 2026-10-17 · Phase 2 · Chunking

- **Goal:** pluggable chunkers whose chunks keep their pages, section and filing metadata (step 2.2, first part).
- **Done:**
  - `copilot.ingest.chunking`: a document is its pages joined by blank lines, so every chunk is a character span with the pages it touches (the page holding most of it first), the section at its start, and the company, fiscal period and form.
  - Three strategies, measured in the embedding model's own tokens: `page` (never crosses a page; long pages split within), `tokens` (windows that cross pages, with overlap, ending at the strongest break in reach: a blank line, then a line end, then a sentence end) and `semantic` (breaks where consecutive lines' embeddings drift apart, merging pieces under 64 tokens).
  - Chunk ids are SHA-256 hashes of strategy, document, span and text; the vector store will use them as point ids, so re-indexing is idempotent.
  - `poe chunk-corpus` for the page and token strategies; the semantic and late-chunking strategies need the embedder and arrive with indexing.
- **Commands:** `uv run poe chunk-corpus --strategy page` (and `tokens-480`, `tokens-256`), `uv run poe check`.
- **Results:**
  - `page`: 23,585 chunks, median 448 tokens. `tokens-480`: 21,899 chunks, median 462 tokens, 52% crossing a page. `tokens-256`: 39,573 chunks, median 242 tokens, 30% crossing a page. Each strategy chunks the 84 documents in 20 to 42 seconds.
  - 236 tests pass offline, 8 of them new.
- **Problems and fixes:**
  - **Long pages.** The median page is 699 tokens, and 72% of pages are longer than the embedder's 512-token window, so a pure one-chunk-per-page strategy would hide the bottom of most pages from dense search. The page strategy therefore splits long pages into windows that stay within the page.
  - **Tiny semantic pieces.** Splitting on lines made every table row its own piece; pieces under 64 tokens now join the next one.
- **Decisions:** none yet; the chunking ADR follows the retrieval experiments.
- **Next:** embedders, the Qdrant index and late chunking (step 2.3).

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
