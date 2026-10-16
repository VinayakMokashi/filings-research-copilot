# Evaluation reports

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

## Runs

Each run writes `items.jsonl`, `summary.json` and `summary.md` to `eval/results/<suite>/<run>/<split>/`. Intervals and tests follow [ADR-0007](../decisions/0007-evaluation-statistics.md); the [runbook](../runbooks/running-evaluations.md) shows the commands.

| Run | Suite | Split | Headline (95% interval) | What it is |
|---|---|---|---|---|
| [first-pages](../../eval/results/retrieval/first-pages/dev/summary.md) | Retrieval | Dev | hit@20 0.29 (0.20 to 0.38) | Floor: the first 20 pages of the correct document |
| [majority](../../eval/results/routing/majority/dev/summary.md) | Routing | Dev | accuracy 0.217 (0.152 to 0.290) | Always the most common route |
| [keyword](../../eval/results/routing/keyword/dev/summary.md) | Routing | Dev | accuracy 0.623 (0.543 to 0.703) | Floor: hand-written keyword rules |
