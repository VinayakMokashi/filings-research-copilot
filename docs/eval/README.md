# Evaluation reports

| Report | Phase | Question |
|---|---|---|
| [Retrieval baseline](retrieval-baseline.md) | 2 | Which chunking, search mode, reranker and context expansion to start from |

One report per experiment, with these sections:

1. **Question:** what we're trying to find out.
2. **Setup:** data, configuration, models, seeds.
3. **Results:** every metric with a 95% bootstrap confidence interval.
4. **Comparison:** the paired difference against the current baseline, and whether it is significant.
5. **Decision:** adopt or reject, with a link to the ADR.
6. **Logs:** where the raw per-question logs live.

## Datasets and splits

| Set | Size | Where | Rule |
|---|---|---|---|
| FinanceBench dev | 100 questions, 20 companies | [`eval/financebench/splits.json`](../../eval/financebench/splits.json) | Used for all tuning and comparisons |
| FinanceBench test | 50 questions, 12 companies | Same file | Held out: opened only at milestones, and each report says whether it was ([ADR-0006](../decisions/0006-evaluation-splits.md)) |
| Routing dev | 138 questions, 46 seeds | [`eval/routing/queries.jsonl`](../../eval/routing/queries.jsonl) | Used for tuning routers ([data card](../data/routing-set.md)) |
| Routing test | 60 questions, 20 seeds | Same file | Held out, like FinanceBench test |
| SQL dev | 28 questions (21 answerable) | [`eval/sql/questions.jsonl`](../../eval/sql/questions.jsonl) | Used for tuning the data agent ([data card](../data/sql-set.md)) |
| SQL test | 14 questions (11 answerable) | Same file | Held out |

## Runs

Each run writes `items.jsonl`, `summary.json` and `summary.md` to `eval/results/<suite>/<run>/<split>/`. Intervals and tests follow [ADR-0007](../decisions/0007-evaluation-statistics.md); the [runbook](../runbooks/running-evaluations.md) shows the commands.

| Run | Suite | Split | Headline (95% interval) | What it is |
|---|---|---|---|---|
| [first-pages](../../eval/results/retrieval/first-pages/dev/summary.md) | Retrieval | Dev | hit@20 0.29 (0.20 to 0.38) | Floor: the first 20 pages of the correct document |
| [page_bge-small-dense-oracle](../../eval/results/retrieval/page_bge-small-dense-oracle/dev/summary.md) | Retrieval | Dev | recall@10 0.630 (0.54 to 0.72); MRR@10 0.423 | Dense search over page chunks within the question's filing: the baseline ([ADR-0011](../decisions/0011-retrieval-baseline.md)) |
| [page_bge-small-dense-corpus](../../eval/results/retrieval/page_bge-small-dense-corpus/dev/summary.md) | Retrieval | Dev | recall@10 0.415 (0.33 to 0.51); MRR@10 0.230 | The same across all 84 filings |
| [page_bge-small-dense-understood](../../eval/results/retrieval/page_bge-small-dense-understood/dev/summary.md) | Retrieval | Dev | recall@10 0.570 (0.48 to 0.67); MRR@10 0.381 | Searching the filings resolved from each question's company, period and form ([guide](../concepts/query-understanding.md)) |
| [tokens-480_bge-small-dense-oracle](../../eval/results/retrieval/tokens-480_bge-small-dense-oracle/dev/summary.md) | Retrieval | Dev | recall@10 0.608 (0.52 to 0.70); MRR@10 0.307 | Dense search over 480-token chunks, the comparison point for the variants |
| [Other retrieval runs](../../eval/results/retrieval/) | Retrieval | Dev | See the [report](retrieval-baseline.md) | BM25, hybrid, rerankers, neighbouring chunks, chunking, late chunking |
| [majority](../../eval/results/routing/majority/dev/summary.md) | Routing | Dev | accuracy 0.217 (0.152 to 0.290) | Always the most common route |
| [keyword](../../eval/results/routing/keyword/dev/summary.md) | Routing | Dev | accuracy 0.623 (0.543 to 0.703) | Floor: hand-written keyword rules |
| [financebench-dev-checks](../../eval/results/facts/financebench-dev-checks.md) | Facts database | Dev | 33 of 33 agree exactly | FinanceBench metrics questions as formulas over annual values |
| [gold](../../eval/results/sql/gold/dev/summary.md) | SQL | Dev | accuracy 1.000 | Gold SQL: a check of the scorer |
| [decline-all](../../eval/results/sql/decline-all/dev/summary.md) | SQL | Dev | accuracy 0.250 (0.107 to 0.429) | Floor: decline everything |
