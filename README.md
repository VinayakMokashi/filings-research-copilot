# The nightly evaluation's history

This branch holds the metrics of the copilot's nightly evaluation, written by the `Nightly evaluation` workflow on `main` ([ADR-0034](https://github.com/VinayakMokashi/filings-research-copilot/blob/main/docs/decisions/0034-nightly-evaluation.md)). It shares no history with `main`, and nothing here deploys.

| File | Contents |
|---|---|
| `nightly/history.jsonl` | One line a night: the set (`slice` or `full`), the commit evaluated, the models, what it cost, its headline metrics with 95% intervals, and its tests against the last full run |
| `nightly/runs/<date>-<set>.json` | The night's per-question scores: ids, route, question type, `correct`, `faithful`, `answered`, cost and seconds; the routing and SQL sets' ids and accuracies |
| `nightly/latest-full.json` | The last complete full run: the baseline each night is tested against |

Only ids, categories and numbers are kept. FinanceBench's questions and answers, and the copilot's answers to them, stay out of this repository under FinanceBench's licence (CC BY-NC 4.0).
