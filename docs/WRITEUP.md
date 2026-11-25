# What worked and what didn't

A technical write-up of the Filings Research Copilot: the choices that held up when measured, the ones that didn't, and what the numbers can and can't say. Every number links to the report that produced it.

## The project in one paragraph

The copilot answers questions about public companies from two sources: the text of their 10-K and 10-Q filings, searched and cited page by page, and their XBRL financial facts, queried with SQL. A LangGraph graph sends each question to a doc agent, a data agent, both, or a crew that writes briefs, and a validator checks every cited sentence before an answer is shown. It runs on Google Cloud, where an idle month costs about $2.10, and it is evaluated on FinanceBench every week. On FinanceBench's held-out test split, opened once with the final version, it answers 34 of 50 questions correctly (0.68, with a 95% interval of 0.56 to 0.80), against 33 for the doc agent alone on the same questions (a difference of +0.02 that can't be told from none, p = 1.00); on the dev split, which its rules were written from, it answers 0.65 (0.56 to 0.74) ([report](eval/financebench-test.md)).

## 1. Fix the exam before writing the code

The evaluation sets came first, in Phase 1, before any retrieval code:

- **FinanceBench's 150 public questions, split by company** into 100 dev questions and 50 held out, so no test company's filings were seen while tuning or training ([ADR-0006](decisions/0006-evaluation-splits.md)). Both sides are checksummed, and the code refuses the test side unless a run asks for it by name.
- **Sets of the project's own** for the parts FinanceBench doesn't test: 198 routing questions and 42 SQL questions with verified gold queries, each with a held-out side ([routing set](data/routing-set.md), [SQL set](data/sql-set.md)).
- **One rule for every change:** report each rate with a 95% bootstrap interval, and adopt a change only on a significant paired gain on the same questions ([ADR-0007](decisions/0007-evaluation-statistics.md)).

This paid for itself twice. It caught the first copilot losing to one of its own components (section 4), and it kept small sets honest: in text2sql-analyst, an earlier project, the same code scored 100% and then 95% on a rerun.

## 2. Retrieval: narrow first, then widen

| Change | Recall@10 on dev | Kept? |
|---|---|---|
| Dense search over page chunks, the question's own filing | 0.630 | The baseline ([ADR-0011](decisions/0011-retrieval-baseline.md)) |
| The same across all 84 filings | 0.415 | |
| Filings resolved from the question's company, period and form | 0.570 | Yes ([guide](concepts/query-understanding.md)) |
| Plus three rewrites (multi-query, HyDE, decomposition), fused | 0.722 (0.63 to 0.81) | Yes ([ADR-0012](decisions/0012-query-understanding-and-rewriting.md)) |
| BM25 fusion; three cross-encoder rerankers | no gain, before or after the rewrites | No ([report](eval/retrieval-baseline.md)) |
| A domain embedder, fine-tuned with hard negatives | 0.747 and 0.742, not significant; worse across all filings | No ([ADR-0027](decisions/0027-domain-embedder.md)) |
| DSPy's MIPROv2 on the HyDE instruction | returned the hand-written one | No ([ADR-0028](decisions/0028-dspy-hyde.md)) |

Page-sized chunks beat 480-token windows (MRR@10 0.423 against 0.307) because a financial statement stays whole on one page. Hybrid search and rerankers are standard advice, and they didn't help here: FinanceBench's questions are templated and name their filing, so finding the right filing mattered far more than ranking passages within it. The fine-tuned embedder learned from synthetic questions about other filings, and that didn't transfer to people's questions.

## 3. Numbers from SQL, not from PDFs

Reading figures off PDF pages is where a language model guesses. The data agent queries XBRL company facts instead:

- **The facts:** SEC company facts normalised into annual values as first reported, with 28 canonical metrics mapped from each company's own tags ([ADR-0008](decisions/0008-xbrl-normalisation.md)). They reproduce all 33 of FinanceBench's dev metric answers as formulas.
- **The agent:** text2sql-analyst, an earlier project, reused as a pinned dependency and improved upstream first ([ADR-0015](decisions/0015-reuse-text2sql-analyst.md)). Value linking (the question's companies, tickers, metrics and fiscal years matched to the database) took execution accuracy on the SQL dev set from 0.61 to 1.00, and it answered all 14 held-out SQL questions (exact interval 0.77 to 1.00) ([guide](concepts/value-linking.md)).
- **Against reading pages:** on FinanceBench's 33 dev figure questions, the data agent answered 32 correctly and the doc agent 29 ([report](eval/data-agent-financebench.md)).

## 4. The first copilot lost to its own component

Version 1 routed each question to the specialists it needed and validated what they wrote. End to end on dev it answered 0.49 correctly, against 0.65 for the doc agent alone on the same questions and judges (p = 0.0003) ([report](eval/copilot-dev.md)). Of the 19 questions it lost to the doc agent, 10 were analyst questions sent to the data agent, which declined them or computed the wrong figure, and 6 were right as first drafted but lost in the validator's revisions.

Version 2 changed only what those losses pointed at ([ADR-0026](decisions/0026-copilot-v2.md)):

- a question the data agent can't answer goes on to the doc agent;
- the router knows the database's grain (annual figures for whole companies), so questions about quarters, segments or judgements go to the filings;
- a checked answer may keep one assessment of its own, labelled apart from the cited facts;
- a revision that would turn an answer into a refusal is set aside.

It answered 0.65 on dev (+16 points, p = 0.0002), as many as the doc agent alone, with 32 of the 33 figure questions right and 82% of its text answers fully supported by their citations, against 49% for the doc agent ([report](eval/copilot-v2.md)). Those rules were written from dev losses, so the held-out test measures how they generalise: on 50 questions from 12 companies never used in tuning, the copilot answered 0.68 (0.56 to 0.80), level with the doc agent alone (0.66), and split the same way as on dev: the data agent won figure questions (16 of 17 against 13), and analyst questions gave a little back ([report](eval/financebench-test.md)).

The lesson: every node in an agent graph is a new way to be wrong. An end-to-end comparison against the simplest baseline, on the same questions, is what found it.

## 5. Faithfulness has a price

The validator checks each cited sentence against its source with a third model, gpt-oss-20b, apart from the writer and the judges. An answer that fails is revised at most twice, then cut to what holds or declined ([ADR-0019](decisions/0019-validator-loop.md)). On the doc agent's dev answers, faithful answers rose from 0.63 to 0.85 (p = 0.0001), and correctness moved from 0.65 to 0.61 (p = 0.28): the loss fell on judgement questions whose verdicts the sources don't state, which is what version 2's labelled assessment answers ([report](eval/validator-dev.md)).

The checker deliberately runs on a different model from the judge. A loop that rewrites until its grader approves would raise the grader's score by construction.

The judge itself is Qwen with a written rubric, and code computes the comparisons of figures. It agreed with all 41 reference labels from a stronger model, a Claude model, and a second judge agreed with 38 ([ADR-0014](decisions/0014-answer-judge.md)). Moved to a second provider, it agreed with itself on 99 of 100 verdicts ([ADR-0024](decisions/0024-second-provider.md)). The reference labels came from a model, not a person, so judge-based numbers carry that caveat, and a person check of the judge is still open.

## 6. What else was measured and left out

| Idea | What happened | Report |
|---|---|---|
| Self-consistency: a vote of three answers on figure questions | 0.879 both ways, at 2.8 times the cost; the wrong answers were wrong the same way every time | [self-consistency](eval/self-consistency.md) |
| A semantic answer cache | a question with its measure swapped looked more like the original than a true paraphrase did, at every usable threshold, so only exact repeats are cached | [guide](concepts/semantic-cache.md) |
| Answer bandits, replayed offline | ε-greedy and UCB1 earned less than the best fixed model at every cost penalty | [bandit routing](eval/bandit-routing.md) |
| The brief crew against one-shot answers | 0.86 of rubric items covered against 0.66, a lead 12 briefs can't make significant | [brief crew](eval/brief-crew.md) |

One fine-tuned model did earn its place: a bge-small classifier trained with LoRA on the LLM router's labels, on a free Kaggle GPU. It routes 0.913 of dev and 0.950 of held-out test questions correctly in 8 ms on a CPU, against 0.739 and 0.800 for the semantic router, so it was adopted as the LLM router's fallback behind a setting ([ADR-0025](decisions/0025-classifier-router.md), [published model](https://huggingface.co/vinayakmokashi45/filings-research-copilot-router)). The deployment still falls back to the semantic router: the classifier learned the first router prompt's labels, and it should be trained again on the current prompt's before it serves.

## 7. Deploying on a shoestring

The deployment is built so that nothing costs money while nobody is using it ([ADR-0031](decisions/0031-google-cloud-topology.md)):

- four Cloud Run services that scale to zero: a public web UI and MCP server, a private API, and an ingestion worker fed by Pub/Sub;
- the facts database built into the API image, with a Cloud SQL copy that runs only during demo windows;
- Firestore for quotas, the answer cache and feedback, and Qdrant Cloud's free tier for the vectors;
- keyless deploys from GitHub Actions through Workload Identity Federation, all in Terraform ([ADR-0032](decisions/0032-continuous-deployment.md)).

Measured from the billing export, an idle month costs about $2.10 before credits, 96% of it the stopped database's storage, and a demo hour $0.014. Under 30 simulated visitors, one API instance served cached answers in 49 ms at the median with no failures ([report](eval/deployment.md)).

Four surprises are worth knowing, each found by measuring:

- Cloud Run's front end answers `/healthz` itself, so a health check on that path never reached the app.
- Cloud SQL reported the instance RUNNABLE six seconds into a ten-minute start, so the start script follows the operation, not the state.
- The deploy's start check pulled the freshly built image back from the registry, at $0.04 of egress a deploy.
- An open Streamlit tab keeps its websocket and bills CPU, about $0.09 an hour, so the UI leaves for a static page after 15 minutes without input; a forgotten tab now costs about $0.023 once.

And one only a recorded demo found: the UI fetched cited pages without signing its call to the private API, so on the live service they couldn't open. Local runs have no private API, so no test had seen it. It was fixed in Phase 10, with a test.

## 8. Online evaluation without users

The nightly evaluation runs in GitHub Actions on a hard spending cap: $0.40 a night, $1.20 for a full Sunday run ([ADR-0034](decisions/0034-nightly-evaluation.md)). It keeps metrics only, since FinanceBench's licence keeps its text out of the repository, and it tests each night against the last full run, question by question. The first complete full run, 22 November, scored 0.66 (0.57 to 0.75), as the dev evaluation did ([report](eval/nightly.md)). After Phase 10 it runs every Sunday.

No readers came, so the online learning had to be fed differently. A daily canary asks the live API ten of the project's own questions, and a judge scores each answer for an answer bandit. Over a week, the bandit's policy earned 0.93 against its randomized fixed arm's 0.85, a difference that can't be told from none (p = 0.25), so by the rule set before the data it stays on ([report](eval/bandit-online.md)). Two caveats go with that: the judge shares its model family with the arm the policy chose, and with cost counted as the offline replay did, the fixed arm would win.

Running it taught three things no offline run could:

- **GitHub's schedules are best-effort.** Runs started hours late, and one never started, so the canary has three slots a day and keeps one.
- **Free quotas roll.** Groq's daily quota cut the first full night short, so a stopped step now waits and resumes.
- **Providers fail in new ways.** A malformed JSON reply from a provider failed a whole answer on the live API, so such an answer now goes out unchecked, marked as unchecked.

## 9. What the numbers can't say

- **Fifty held-out questions** give intervals of about ±0.13, and FinanceBench's questions are templated, so the test result shows the copilot generalises to new companies, not that it would hold on any question an analyst might ask.
- **The judge** was checked against a stronger model's labels, not a person's.
- **The faithfulness check can't read SQL answers,** which cite a query, not sentences, so the copilot's faithfulness is reported on its text answers.
- **The corpus** is FinanceBench's: 361 filings from 40 companies ([data card](data/financebench.md)), and the facts database holds annual figures for whole companies only.
- **The online numbers come from the project's own questions,** since no reader asked, rated or searched while they were measured.

## 10. With hindsight

- Label 20 answers by hand in the first week, before trusting any judge.
- Build the end-to-end evaluation before the graph, not after it.
- Cite query results as sources, so the faithfulness check can read data answers too.
- Make the deployed service's smoke test open a cited page, not only ask a question.

## Where the numbers come from

| Number | Report |
|---|---|
| 34 of 50 held-out questions correct, against 33 for the doc agent | [FinanceBench's test split](eval/financebench-test.md) |
| 0.65 correct on dev; 82% of text answers fully supported | [copilot v2](eval/copilot-v2.md) |
| Recall@10 0.722 | [retrieval](eval/retrieval-baseline.md), [ADR-0012](decisions/0012-query-understanding-and-rewriting.md) |
| SQL 1.00 on dev, 14 of 14 held out; 32 of 33 figure questions | [SQL test run](../eval/results/sql/sql-agent-v2/test/summary.md), [data agent](eval/data-agent-financebench.md) |
| Routing 60 of 60 held out; classifier 0.950 | [routing](eval/routing.md), [LoRA router](eval/lora-router.md) |
| $2.10 an idle month; $0.014 a demo hour | [deployment](eval/deployment.md#costs) |
| 0.66 nightly baseline | [nightly](eval/nightly.md) |
| Bandit 0.93 against 0.85 | [bandit online](eval/bandit-online.md) |
