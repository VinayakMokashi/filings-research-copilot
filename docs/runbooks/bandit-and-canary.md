# The answer bandit and the daily canary

How the online answer bandit and the canary that feeds it are switched on and off, watched, and reported on ([ADR-0036](../decisions/0036-bandit-online.md), [guide](../concepts/bandit-routing.md)), and how preference pairs are exported ([ADR-0035](../decisions/0035-preference-pairs.md), [guide](../concepts/preference-data.md)).

## What runs

| Part | Where | What it does |
|---|---|---|
| The bandit | The API, when `FRC_BANDIT_DAILY_USD` is above 0 (Terraform's `bandit_daily_usd`, 0.25) | Chooses the doc agent's answer arm on Cerebras: a coin flip between the fixed arm and ε-greedy. It logs each answer an arm writes, judges a sample, and learns from the judge and from thumbs |
| Its cap | Firestore `quotas/<day>.bandit_usd` | The arms' and the judge's calls, at most $0.25 a UTC day. At the cap, answers take the fixed path on Groq |
| Its state | Firestore `bandit/answer-arms` | Each arm's count of rewards and their sum |
| Its log | Firestore `bandit-answers/<request id>` | The arm, the group (`policy`, `control`, `retry`), canary or visitor, the cost, and the rewards (`judge`, `thumbs`) |
| The canary | `.github/workflows/canary.yml`, 04:17 UTC (09:47 IST), as `github-canary` | Ten of the routing set's 30 dev questions on the doc route a day, in turn, through the live API; metrics to `eval-history` (`canary/`) |

## Switch the bandit on or off

The cap is a Terraform variable in `infra/terraform/envs/prod/variables.tf`.

1. Set `bandit_daily_usd` (0 is off) in a pull request, merge it, and apply prod from a clean worktree of `origin/main`, plan first ([deploy runbook](deploy.md)). The API gets a new revision on the same image.
2. Switch the canary with it: `gh workflow disable canary.yml` when the bandit goes off, `gh workflow enable canary.yml` when it comes back. It is approved only while the bandit is on.

The arms' statistics stay in Firestore, so a bandit switched on again starts from what it learned.

## Run a canary trial

A trial asks fewer than ten questions and keeps nothing:

```bash
gh workflow run canary.yml -f questions=2
gh run watch "$(gh run list --workflow canary.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

The job summary has a row per question: route, arm, group, answered, judged, faithful and seconds. A trial spends like any canary question, inside the bandit's cap.

On the laptop, against a local API (`poe api` on port 8010): `uv run poe canary --api-url http://127.0.0.1:8010 --per-day 2 --out dist/canary`.

## Watch it

- **The day's spend:** `quotas/<day>.bandit_usd` in the Firestore console, or the API's logs: `gcloud logging read 'jsonPayload.event="llm.spend"' --format="value(jsonPayload.label,jsonPayload.cost_usd)"` with the `frc` configuration.
- **What it has learned:** `bandit/answer-arms` in the Firestore console: `count_<arm>` and `sum_<arm>` (arms with `-` written as `_`).
- **The canary's days:** `canary/history.jsonl` on the `eval-history` branch, a line a day. `curl -s https://raw.githubusercontent.com/VinayakMokashi/filings-research-copilot/eval-history/canary/history.jsonl`.

## When the canary fails

An issue labelled `canary-failure` lists the questions whose requests failed and the error: an HTTP status, an `error` event, or no answer. A busy API (a visitor's question was running) is noted and doesn't fail the day.

1. **Is the service up?** `uv run --no-sync python ../private/tools/check_live.py`, or the deploy runbook's checks.
2. **Read the API's logs** around the run's time for `api.ask_failed`, `llm.error` or `bandit.arm_failed`.
3. **Run a trial** once the cause is fixed, then close the issue with the cause.

## The two-week report

After 14 days with the canary running:

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=frc uv run poe bandit-report --since 2026-11-16 --until 2026-11-30
```

It reads the log as the owner, keeps a copy under `data/processed/bandit/`, and writes `eval/results/bandit-online/two-weeks/summary.json`: each group's answers and arms, the mean reward of each kind with intervals, the policy's difference from the control with a permutation test, and the decision by ADR-0036's rule. The report `docs/eval/bandit-online.md` is written from it. If the rule says off, switch the bandit and the canary off as above.

## Export preference pairs

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=frc uv run poe export-preferences
uv run poe export-preferences --from data/processed/preferences/firestore --runs copilot-v2
```

The first reads the deployment's ratings and picks as the owner and keeps a copy; the second reads that copy and adds local runs' validator pairs. Both write `data/processed/preferences/pairs.jsonl` and `pairs-meta.jsonl` ([data card](../data/preference-pairs.md)). Nothing they write is committed.

## Costs

The bandit's calls and its judge's are billed by Cerebras, at most $0.25 a day; the canary alone should cost $0.05 to $0.08 a day. The nightly evaluation and the paid fallback spend from the same key under their own caps, so Cerebras's own console shows all three together.
