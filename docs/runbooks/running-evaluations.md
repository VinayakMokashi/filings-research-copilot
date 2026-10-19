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

A routing predictions file has one line per dev question: `{"id": "r001", "route": "doc"}`. Runs land in `eval/results/routing/<run>/<split>/`, with accuracy overall, by route and by origin (seed or paraphrase). The set itself is fixed: rebuilding it needs `poe build-routing-set --force` and a note in the build log.

## Score SQL

Needs the facts database (`uv run poe build-facts`).

```bash
uv run poe eval-sql --baseline gold           # 100%: checks the scorer
uv run poe eval-sql --baseline decline-all
uv run poe eval-sql --predictions answers.jsonl --run sql-agent-v1
```

Each line of a predictions file is `{"id": "s01", "sql": "SELECT ..."}`, or `{"id": "s33", "declined": true}` to decline. Queries run read-only with a step limit. Runs land in `eval/results/sql/<run>/<split>/`, with accuracy overall, for answerable and unanswerable questions, and by difficulty. After rebuilding the facts database, `uv run pytest -m integration` confirms every gold query still returns its recorded rows.

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

## Compare two runs

```bash
uv run poe compare-runs eval/results/retrieval/first-pages/dev eval/results/retrieval/hybrid-v1/dev --metric recall@10
```

The output gives both means, the difference with its 95% interval, the p-value from a paired permutation test, and a verdict at α = 0.05 ([ADR-0007](../decisions/0007-evaluation-statistics.md)). A change ships when the verdict is "significant improvement".

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
