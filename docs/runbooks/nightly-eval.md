# The nightly evaluation

How the copilot is evaluated on a schedule, how to run a night by hand, and what to do when one fails or finds a regression ([ADR-0034](../decisions/0034-nightly-evaluation.md), [guide](../concepts/online-evaluation.md)). From 12 to 25 November the evaluation ran every night; since Phase 10's close it runs every Sunday, always as a full run ([ADR-0034's amendment](../decisions/0034-nightly-evaluation.md#amendment-25-november-a-full-run-every-sunday-after-phase-10)).

## What runs

| | Every Sunday (IST), on schedule | A slice, by hand |
|---|---|---|
| When | 20:30 UTC on Saturday, 02:00 IST on Sunday | When asked (`set: slice`) |
| FinanceBench dev | All 100 questions | The 32-question slice in `eval/nightly/slice.json` |
| Routing and SQL sets | Their dev splits: 138 and 28 questions | The same |
| Cap | $1.20 | $0.40 |
| Waiting | Up to 3 hours in all, for a model that stopped a step | The same |

The workflow is `.github/workflows/nightly.yml`. Its name and the history's file names still say "nightly", from the two weeks it ran every night.

- **When it really starts.** GitHub may start a scheduled run late when its runners are busy: the first three nights started 4.5 to 5.5 hours after 20:30 UTC. The set and the night's date are read in IST when the run starts, so a start up to about 22 hours late still runs the right set under the right date.

- **Access:** it acts as the `github-eval` account, through workload identity federation, from `main` only.
- **Data:** it reads the data bundle named in `infra/data-bundle.json` (cached in Actions by that name) and FinanceBench's question files.
- **Results:** it pushes the night's metrics to the `eval-history` branch, and its job summary shows them with each step's spend.

## Run a trial

A trial runs every step under a small cap and keeps nothing, so it tests the pipeline for a few cents:

```bash
gh workflow run nightly.yml -f set=slice -f budget=0.02
gh run watch "$(gh run list --workflow nightly.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

A trial's cap must be above 0 and at most the set's. Its steps stop at their shares of it, so the night ends partial: that is expected.

## Run a night on the laptop

A night must start from an empty cache, or earlier replies replay for free and it measures nothing. So it runs from a fresh data folder holding only what a CI runner has:

```bash
mkdir -p dist/nightly-data/raw/financebench
tar -xzf dist/api-data.tar.gz -C dist/nightly-data      # the bundle in infra/data-bundle.json
cp -r data/raw/financebench/data dist/nightly-data/raw/financebench/

export FRC_DATA_DIR=dist/nightly-data
export FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b
export FRC_LLM_TOKENS_PER_MINUTE=25000 HF_HUB_OFFLINE=1
export FRC_QDRANT_URL=... FRC_QDRANT_API_KEY=...       # Qdrant Cloud, the read-only key
uv run poe nightly-eval --set slice --budget 0.40 --out dist/nightly/<date>-slice
```

- **Output.** It writes `night.json`, `history.json`, the ledger and each step's log under `--out`. A night run by hand records `runner: local`.
- **Resuming.** Run the same command again, and each step skips the questions it has done.
- **One at a time.** Never start a second copy while one runs: both would write the same files.

## Read the history

The `eval-history` branch holds:

| File | Contents |
|---|---|
| `nightly/history.jsonl` | One line a night: the set, the commit, the models, the cost by model, the summary with intervals, the tests and the verdict |
| `nightly/runs/<date>-<set>.json` | The same, with the per-question scores |
| `nightly/latest-full.json` | The last complete full run, which the next nights are tested against |

The project page draws the trend from `history.jsonl`. A partial night (cut short by its cap, or with a failed step) shows as a hollow point and draws no verdict.

## Drift

Each night's line in `history.jsonl` carries its drift checks ([ADR-0037](../decisions/0037-drift-checks.md)): retrieval similarity and refusals, the first three nights that recorded each against the last three. The canary's days carry latency and similarity the same way. A drift is reported, not alarmed.

- **Look by hand**, with any window: `uv run poe drift-check` (reads the branch from git) or `uv run poe drift-check --window 5`.
- **When similarity drifts,** something moved under the search: compare `infra/data-bundle.json` and the index card between the reference nights' commits and the recent ones, and check the collection in Qdrant Cloud.
- **After a deliberate change** (a new collection, a re-index), the old reference reads as drift ever after. Note the date in the build log; the checks show the step at that date.

## When an issue says "regression"

The issue lists each tested metric: the baseline, the night, the difference and its Holm-adjusted p-value.

1. **Find what changed** since the baseline. Compare the night's `commit` with the baseline's, the models (`models` in the night's file), and `infra/data-bundle.json`.
2. **Look at the questions.** Open both nights' files from `eval-history` and list the ids that went from 1 to 0.
3. **Decide.**
   - If a merged change caused it, fix or revert it.
   - If a provider did, compare the replies' lengths and settings, as ADR-0024's check did.
   - If it was chance, say so on the issue.
4. **Close the issue** with the cause. The next regression opens a new one.

## When a night fails

- **Which step.** The job summary lists each step's exit code and spend. A failed step's line names its exception's class only: its log stays on the runner, since it could quote a question.
- **A model stopped a step** (exit 75). The step ran again every ten minutes, carrying on where it stopped, until the night had waited three hours. The summary's "Run again" column counts the reruns.
  - The error reads "a model's quota stayed spent" (most likely Groq's free quota for the small model) or "a model call kept failing" (an outage).
  - The night is partial and draws no verdict. Nothing needs doing unless it repeats.
  - A rerun the same day meets the same quota.
- **Reproduce it** on the laptop with the same commit (above), where the step's log is at hand.
- **Run it again** for the same night with `gh run rerun <id>`. The night's metrics are pushed only after the run ends.

## Change it

- **The slice:** `uv run poe nightly-slice --size N`, then commit `eval/nightly/slice.json`. Comparisons with the last full run still hold, since every slice question is a dev question.
- **The steps' shares:** `copilot.eval.nightly.steps`.
- **The caps** were set by the owner (ADR-0034). Raising one needs the owner's yes; when a night costs more than its cap, shrink the slice instead.
- **Stop it:** `gh workflow disable nightly.yml`; `gh workflow enable nightly.yml` starts it again.

## Costs

- **Each night's cost** is in its file (`spent_usd`, and `spent_by_model`). Groq's free calls count at list price there.
- **The page** shows the month's Cerebras spend.
- **Cerebras's own console** has the bill. The nightly run, the bandit and the paid fallback all spend from the same key, so its total covers all three.
