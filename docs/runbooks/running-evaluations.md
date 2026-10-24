# Running evaluations

How to score a system on FinanceBench, read the results, and decide whether a change is better.

## Before you start

```bash
uv sync
uv run poe fetch-financebench     # question files and the PDFs they cite, each verified (159 MB)
```

The dev/test split is committed in `eval/financebench/splits.json`. Never regenerate it: the held-out test set depends on it staying fixed ([ADR-0006](../decisions/0006-evaluation-splits.md)).

## Score retrieval

The built-in floor ranks the first 20 pages of the correct document:

```bash
uv run poe eval-retrieval --baseline first-pages
```

To score your own retriever, write one JSON line per dev question, with pages ranked best first and counted from 0:

```json
{"id": "financebench_id_03029", "pages": [{"doc_name": "3M_2018_10K", "page": 59}, {"doc_name": "3M_2018_10K", "page": 60}]}
```

Then run:

```bash
uv run poe eval-retrieval --predictions my_predictions.jsonl --run hybrid-v1
```

The file must cover exactly the questions in the split; a missing or extra id stops the run. Each run writes three files to `eval/results/retrieval/<run>/<split>/`:

| File | Contents |
|---|---|
| `items.jsonl` | One row per question: id, question type, every metric, the top 20 pages |
| `summary.json` | The system, the split, and each metric's mean with its 95% interval, overall and by question type |
| `summary.md` | The same summary as tables |

### Run the project's own retrievers

With an index built (`poe index-corpus`, see the [ingestion runbook](ingesting-filings.md)), `poe run-retrieval` searches for every dev question and scores the result in one step:

```bash
uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode dense
uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode hybrid --setting corpus
uv run poe run-retrieval --collection fb_tokens-480_bge-small --mode dense --rerank jina-turbo --rerank-top 30
```

| Option | Meaning |
|---|---|
| `--mode dense`, `bm25` or `hybrid` | Which vectors to search; hybrid fuses both with RRF (k = 60), `--rrf-weights 2,1` weights the lists |
| `--setting oracle`, `corpus` or `understood` | Search only the question's own filing (default), every filing in the collection, or the filings resolved from the question's company, period and form |
| `--rerank KEY` and `--rerank-top N` | Reorder the top N candidates with a cross-encoder: `minilm-l6`, `minilm-l12`, `jina-turbo` or `bge-base` |
| `--neighbours 1` and `--neighbours-top 5` | Follow each of the top 5 hits with its neighbouring chunks |
| `--rewrite multi`, `hyde`, `decompose` or `all` | Also search model-written rewrites and fuse every ranking; calls go through the cache in `data/cache/llm.jsonl` and are paced for the free tier |
| `--rerank-query rewrite` | Rerank against the first multi-query rewrite instead of the question |

The run name is built from the options (for example `tokens-480_bge-small-hybrid-corpus`), and the summary records the configuration, the index's models and each question's latency. Searching is cheap; reranking runs a model for every candidate, so on a laptop CPU a reranked run takes 10 minutes to an hour.

## Score routing

```bash
uv run poe eval-routing --baseline keyword        # or --baseline majority
uv run poe eval-routing --predictions routes.jsonl --run llm-router-v1
```

A routing predictions file has one line per dev question: `{"id": "r001", "route": "doc"}`. Runs land in `eval/results/routing/<run>/<split>/`, with accuracy overall, by route and by origin (seed or paraphrase), and a confusion matrix in `confusion.md`. The set itself is fixed: rebuilding it needs `poe build-routing-set --force` and a note in the build log.

The copilot's own routers ([guide](../concepts/semantic-routing.md)) run with `poe run-router`:

```bash
uv run poe run-router --router semantic --mask entities --method centroid --run semantic-masked-centroid
uv run poe run-router --router semantic --k 5 --run semantic-k5              # a vote of the 5 nearest
uv run poe run-router --router llm --run llm-qwen3.8-27b                     # needs GROQ_API_KEY
FRC_LLM_FAST_MODEL=groq/openai/gpt-oss-20b uv run poe run-router --router llm --run llm-gpt-oss-20b
uv run poe run-router --router cascade --mask entities --method centroid --threshold 0.05 --run NAME
```

| Option | Effect |
|---|---|
| `--method vote` (with `--k N`) or `centroid` | A similarity-weighted vote of the N nearest examples, or the nearest route centroid |
| `--mask entities` | Replace company names and years before embedding |
| `--instruction` | Embed questions with bge's search instruction |
| `--threshold T` | For a cascade, the confidence the semantic route needs before the LLM is skipped |

The semantic router's examples are the dev questions, and each one is routed with its own seed group left out. The LLM router's calls are cached in `data/cache/router.jsonl` and paced; each decision is appended to `data/processed/routing/<run>/<split>/decisions.jsonl`, so a run stopped by a quota resumes where it stopped. A run name is tied to its configuration: resuming it with other options stops with an error.

## Score SQL

Needs the facts database (`uv run poe build-facts`).

```bash
uv run poe eval-sql --baseline gold           # 100%: checks the scorer
uv run poe eval-sql --baseline decline-all
uv run poe eval-sql --predictions answers.jsonl --run sql-agent-v1
```

Each line of a predictions file is `{"id": "s01", "sql": "SELECT ..."}`, or `{"id": "s33", "declined": true}` to decline. Queries run read-only with a step limit. Runs land in `eval/results/sql/<run>/<split>/`, with accuracy overall, for answerable and unanswerable questions, and by difficulty. After rebuilding the facts database, `uv run pytest -m integration` confirms every gold query still returns its recorded rows.

The data agent ([ADR-0015](../decisions/0015-reuse-text2sql-analyst.md)) answers the set and scores itself in one step:

```bash
uv run poe run-sql-agent                         # dev, run sql-agent-v2 (needs GROQ_API_KEY)
uv run poe run-sql-agent --run sql-agent-v1 --no-linking   # the baseline, without value linking
uv run poe run-sql-agent --run sql-agent-v3 --limit 5
```

Each response is appended to `eval/results/sql/<run>/<split>/trace.jsonl` as it arrives, with the agent's status, the tables it used, its SQL attempts, tokens and model time; a rerun skips answered questions, and a run stopped by a daily quota exits with a message and carries on when run again. The run then writes `predictions.jsonl` (for `poe eval-sql`) and the scored run beside it, with accuracy by category too. Model calls are cached in `data/cache/sql.jsonl`. These files hold the project's own questions and the model's SQL, so they are committed.

To put one question of your own to the data agent ([guide](../concepts/text-to-sql-agent.md)):

```bash
uv run poe ask-data "How did 3M's capital expenditure change from fiscal 2018 to fiscal 2022?"
uv run poe ask-data "..." --json      # the whole typed answer, as other components get it
```

It prints the status and the written answer, the SQL, the rows (the first 20), exact statistics for each measure column with the rows where its extremes fall, and the suggested chart:

```text
[ok] 3M's capital expenditure increased from $1.577 billion in fiscal 2018 to $1.749 billion
in fiscal 2022, representing an overall growth of $172 million (10.9%).
  ...
fiscal_year | capital_expenditure | change_from_2018
2018 | 1577000000.0 | 0.0
  ...
capital_expenditure: total 8,129,000,000.00, mean 1,625,800,000.00, min 1,501,000,000.00,
max 1,749,000,000.00, max at 2022, min at 2020
Chart: line of capital_expenditure by fiscal_year
```

The status is `ok`, `unanswerable` (declined, with the reason) or `error` (the query still failed after two repairs, or a quota stopped the call), and `error` exits with code 1. The calls share the cache in `data/cache/sql.jsonl`, so asking the same question again costs no tokens.

## Answer dev questions

The doc agent ([grounded generation](../concepts/grounded-generation.md)) answers each dev question from the filings, and `poe answer-questions` scores what it can without a judge:

```bash
uv run poe eval-context                        # is an evidence page in the context? by budget
uv run poe answer-questions --limit 10         # a smoke run on the first 10 dev questions
uv run poe answer-questions                    # all dev questions
uv run poe answer-questions --run doc-agent-v2 # a new run, after changing the agent
```

Both need Qdrant with the `fb_page_bge-small` collection and `GROQ_API_KEY`. Every model call goes through the cache in `data/cache/llm.jsonl`, so the rewrites cost tokens only the first time.

- **Resumable.** Each answer is appended to `data/processed/answers/<run>/dev/answers.jsonl` as soon as it arrives, and a rerun skips the questions already there. A run stopped by a daily quota continues with the same command the next day.
- **Paced.** After each uncached call the run waits until the tokens-a-minute limit has earned back what the call used (`FRC_LLM_TOKENS_PER_MINUTE`, 8,000 by default). On Groq's free tier that is about 30 seconds an answer, and the daily cap of about 200,000 tokens allows about 35 questions a day, retries included.
- **What is committed.** The answers file holds filing text and model answers, so it stays local. `eval/results/answers/<run>/dev/` holds only ids and numbers: `answered`, `retried`, `context_hit`, `cites_evidence`, citation counts, invalid citations, failed calculations, tokens and latency.
- **Correctness** needs the LLM judge (step 3.6); these measures are structural.

The data agent ([guide](../concepts/text-to-sql-agent.md)) answers the same questions with SQL over the facts database instead, and writes its answers in the same shape, so the same judge grades them:

```bash
uv run poe answer-with-data --limit 3 --run data-agent-smoke   # a smoke run
uv run poe answer-with-data                    # the 33 dev metrics questions, run data-agent-v1
uv run poe answer-with-data --types all --run data-agent-all   # every dev question
uv run poe judge-answers --run data-agent-v1
```

It needs the facts database (`poe build-facts`) and `GROQ_API_KEY`, not Qdrant. The written answer comes from the strong model, the doc agent's answer model, unless `--analysis-model fast` says otherwise; that keeps a comparison of the two agents to where their numbers come from. Calls are cached in `data/cache/sql.jsonl`. It resumes like the doc agent's runs, and stops with a message when a daily quota runs out. About 4,500 tokens a question. `eval/results/answers/<run>/dev/` holds ids and numbers only: `answered`, `declined`, `failed`, `repaired`, tokens, model latency and cost at list prices; the SQL and rows stay in the local answers file, since they restate the questions' figures.

## Answer the hybrid questions

The [hybrid set](../data/hybrid-set.md) holds thirteen questions that need figures and an explanation. The hybrid agent answers them from the data agent's query result and the doc agent's pages together; the doc agent alone answers them for comparison:

```bash
uv run poe run-hybrid --agent hybrid --run hybrid-smoke --limit 2   # a smoke run
uv run poe run-hybrid --agent hybrid --run hybrid-v1
uv run poe run-hybrid --agent doc --run doc-agent-v4
uv run poe compare-runs eval/results/hybrid/doc-agent-v4/dev eval/results/hybrid/hybrid-v1/dev --metric all_figures
```

Both need Qdrant, the facts database and `GROQ_API_KEY`. Each run answers every question, appending to `data/processed/hybrid/<run>/answers.jsonl`, then checks each answer's sentences against the sources it cites, into `faithfulness.jsonl` beside it; both steps resume where they stopped, and a quota or an outage stops the run with a message. `eval/results/hybrid/<run>/dev/` gets the per-question checks (`figures_given`, `all_figures`, `database_cited`, `pages_cited`, `faithful`, `supported`), costs, and `answers.jsonl` with each answer's text, the labels of the sources it cites and the hybrid agent's SQL and rows. These are the project's own questions, so the answers are committed; the pages' text stays local.

## Judge answers and check the judge

The judge ([guide](../concepts/llm-as-judge.md)) grades a run's answers against FinanceBench's reference answers; a sample of reference labels checks the judge:

```bash
uv run poe judge-answers --run doc-agent-v3-full                         # the default judge (fast role)
FRC_LLM_FAST_MODEL=groq/openai/gpt-oss-20b uv run poe judge-answers --run doc-agent-v3-full   # a second judge
uv run poe label-sample --run doc-agent-v3-full                          # the labelling sample, and what the labeller sees
uv run poe judge-agreement --run doc-agent-v3-full --judge qwen3.8-27b-p2 --judge gpt-oss-20b-p2
```

- **Resumable and named.** Verdicts are appended to `data/processed/judgements/<run>/<judge>/judgements.jsonl` as they arrive; the judge's name joins the model and the prompt version (`qwen3.8-27b-p2`), so a new rubric never resumes an old one. Outcomes by id go to `eval/results/correctness/<run>--<judge>/dev/`.
- **Its own cache.** The judge caches its calls in `data/cache/judge.jsonl`, so it can run while an answer run writes `data/cache/llm.jsonl`.
- **Labels.** `eval/labels/answer-correctness.jsonl` holds one line per labelled answer: id, answers run, labeller and label. The sample's ids are in `answer-correctness-sample.json`; the labeller sees exactly what the judge sees, never its verdicts. The current labels came from a stronger model, not a person ([data card](../data/answer-labels.md)).
- **Cost.** About 660 tokens a verdict on the fast model, about 66,000 for a 100-question run.

Two more passes read the same answers:

```bash
uv run poe check-faithfulness --run doc-agent-v4-full      # each sentence against the pages it cites
uv run poe analyse-errors --run doc-agent-v4-full --judge qwen3.8-27b-p2 --faithfulness qwen3.8-27b-f1
```

`check-faithfulness` makes one call per answered question (about 1,300 tokens), resumably, with its own cache file (`data/cache/faithfulness.jsonl`); `analyse-errors` makes none, and adds error categories, model latency and cost at list prices. A change to what happens after the model replies, such as the calculator, can be re-scored at no cost: a new `--run` name replays every model call from the cache.

## Compare two runs

```bash
uv run poe compare-runs eval/results/retrieval/first-pages/dev eval/results/retrieval/hybrid-v1/dev --metric recall@10
```

The output gives both means, the difference with its 95% interval, the p-value from a paired permutation test, and a verdict at α = 0.05 ([ADR-0007](../decisions/0007-evaluation-statistics.md)). A change ships when the verdict is "significant improvement". For a yes-or-no metric it also counts the questions both runs get, each run alone, and neither.

Two runs must cover the same questions. To compare runs over different sets, such as the doc agent on all dev questions and the data agent on the metrics questions, keep the questions they share with `--where`:

```bash
R=eval/results/correctness
uv run poe compare-runs $R/doc-agent-v4-full--qwen3.8-27b-p2/dev $R/data-agent-v1--qwen3.8-27b-p2/dev \
  --metric correct --where question_type=metrics-generated
```

When one experiment tries several variants against the same baseline, compare them as a family, so their p-values are adjusted together (Holm):

```bash
R=eval/results/retrieval
uv run poe compare-family $R/tokens-480_bge-small-dense-oracle/dev \
  $R/tokens-480_bge-small-bm25-oracle/dev $R/tokens-480_bge-small-hybrid-oracle/dev \
  --metric recall@10 --title "Search mode" --out $R/_comparisons/mode-oracle
```

Include every variant that was tried, including the ones that did badly; leaving them out would understate the chance of a false win.

## Milestone evaluations on the test split

Open the test split only at the end of a milestone, once the system is frozen:

```bash
uv run poe eval-retrieval --predictions final.jsonl --run phase2-final --split test --allow-test
```

The run's summary records that the held-out split was opened. Say so in the eval report and the build log too.

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `doesn't match the manifest` | A local file is corrupt or changed. Run `uv run poe fetch-financebench` again. |
| `The test split is held out` | You asked for `--split test` without `--allow-test`. That's deliberate: see above. |
| `Predictions don't match the questions` | The predictions file must have exactly one line per question in the split. |
| `llm.error ... rate_limited=True` during `answer-questions` | The model's tokens-a-minute or daily cap was reached. The call is retried after 30, 60 and 90 seconds; if it still fails, the run stops with the answers so far saved. Once the daily cap resets, run the same command again and it carries on. |
| `differ from the ones the split recorded` | The local question file no longer matches the checksums in the split file. Fetch again. |
