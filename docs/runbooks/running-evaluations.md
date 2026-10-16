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

## Compare two runs

```bash
uv run poe compare-runs eval/results/retrieval/first-pages/dev eval/results/retrieval/hybrid-v1/dev --metric recall@10
```

The output gives both means, the difference with its 95% interval, the p-value from a paired permutation test, and a verdict at α = 0.05 ([ADR-0007](../decisions/0007-evaluation-statistics.md)). A change ships when the verdict is "significant improvement". When one experiment tries several variants against the same baseline, adjust their p-values together with `copilot.eval.stats.holm` before reading the verdicts.

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
| `differ from the ones the split recorded` | The local question file no longer matches the checksums in the split file. Fetch again. |
