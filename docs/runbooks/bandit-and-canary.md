# The answer bandit and the daily canary

How the online answer bandit and the canary that feeds it are switched on and off, watched, and reported on ([ADR-0036](../decisions/0036-bandit-online.md), [guide](../concepts/bandit-routing.md)), and how preference pairs are exported ([ADR-0035](../decisions/0035-preference-pairs.md), [guide](../concepts/preference-data.md)).

## What runs

| Part | Where | What it does |
|---|---|---|
| The bandit | The API, when `FRC_BANDIT_DAILY_USD` is above 0 (Terraform's `bandit_daily_usd`, 0.25) | Chooses the doc agent's answer arm on Cerebras: a coin flip between the fixed arm and ε-greedy. It logs each answer an arm writes, judges a sample, and learns from the judge and from thumbs |
| Its cap | Firestore `quotas/<day>.bandit_usd` | The arms' and the judge's calls, at most $0.25 a UTC day. At the cap, answers take the fixed path on Groq |
| Its state | Firestore `bandit/answer-arms` | Each arm's count of rewards and their sum |
| Its log | Firestore `bandit-answers/<request id>` | The arm, the group (`policy`, `control`, `retry`), canary or visitor, the cost, and the rewards (`judge`, `thumbs`) |
| The canary | `.github/workflows/canary.yml`, at 04:17 UTC (09:47 IST), with backup slots at 08:17 and 12:17 UTC, as `github-canary` | Ten of the routing set's 30 dev questions on the doc route a day (twenty on the weekdays of 16 to 20 November), in turn, through the live API; metrics to `eval-history` (`canary/`). The first slot to run asks; a later one finds the day kept and stops |

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

The job summary has a row per question: route, arm, group, answered, judged, faithful and seconds. A trial spends like any canary question, inside the bandit's cap. It also counts against the canary's twenty questions a day (UTC), so on a day of twenty (17 to 20 November) it would leave the day's last questions an HTTP 429: run trials on a day of ten.

On the laptop, against a local API (`poe api` on port 8010): `uv run poe canary --api-url http://127.0.0.1:8010 --per-day 2 --out dist/canary`.

## Watch it

- **The day's spend:** `quotas/<day>.bandit_usd` in the Firestore console, or the API's logs: `gcloud logging read 'jsonPayload.event="llm.spend"' --format="value(jsonPayload.label,jsonPayload.cost_usd)"` with the `frc` configuration.
- **What it has learned:** `bandit/answer-arms` in the Firestore console: `count_<arm>` and `sum_<arm>` (arms with `-` written as `_`).
- **The canary's days:** `canary/history.jsonl` on the `eval-history` branch, a line a day. `curl -s https://raw.githubusercontent.com/VinayakMokashi/filings-research-copilot/eval-history/canary/history.jsonl`.

## A day with no canary

GitHub may start a scheduled run hours late or drop it, as it dropped the first day's (15 November), so the canary has three slots. If a day still has no line by the evening, ask it by hand before midnight UTC (05:30 IST), when the canary's day ends:

```bash
gh workflow run canary.yml
```

Without a number it asks the day's: twenty on the weekdays of 16 to 20 November, ten on any other day. The job "Choose the day" reads `canary/history.jsonl` first. A full run, scheduled or by hand, stops at a day already kept, so a day is never asked twice; a trial always asks, and keeps nothing. Identity federation lets only `main` call the API, so a run from another branch fails at its sign-in.

A day is a date in UTC, like the API's daily quotas. The canary asks as the visitor `canary`, which the API allows twenty questions a day from midnight UTC (`FRC_API_DAILY_QUESTIONS`), so a day of twenty uses the whole quota. A slot that GitHub starts hours late still asks for its own date.

## When the canary fails

An issue labelled `canary-failure` lists the questions whose requests failed and the error: an HTTP status, an `error` event, or no answer. A busy API (a visitor's question was running) is noted and doesn't fail the day.

1. **Is the service up?** `uv run --no-sync python ../private/tools/check_live.py`, or the deploy runbook's checks.
2. **Read the API's logs** around the run's time for `api.ask_failed`, `llm.error` or `bandit.arm_failed`. `api.ask_failed` carries the traceback; `llm.error` says which role failed, and whether it was a spent quota (`rate_limited`) or a reply the provider refused as invalid JSON (`invalid_reply`).
3. **Run a trial** once the cause is fixed, then close the issue with the cause.

The first failure (#122, 15 November) was a model's slip, not an outage: Groq refused the answer check's reply as invalid JSON, and the whole answer failed. Since #123 the API lets such an answer out unchecked instead.

The second (#126, 16 November) was the canary's own quota. GitHub started 15 November's last slot at 18:48 UTC, after midnight IST, and the canary then took its day from the IST date. So it asked 16 November's twenty questions on 15 November's quota, which eleven questions had already used; the last eleven got HTTP 429 before any model call. Since #127 the day is the date in UTC. An HTTP 429 always means a daily quota is used up: the canary's twenty, or everyone's 200.

## The comparison's report

After the canary's days from 15 to 22 November, a week since [ADR-0036's amendment](../decisions/0036-bandit-online.md#amendment-15-november-a-week-instead-of-two) (`--until` is the first day left out):

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=frc uv run poe bandit-report --since 2026-11-15 --until 2026-11-23 --name one-week
```

It reads the log as the owner, keeps a copy under `data/processed/bandit/`, and writes `eval/results/bandit-online/one-week/summary.json`: each group's answers and arms, the mean reward of each kind with intervals, the policy's difference from the control with a permutation test, and the decision by ADR-0036's rule. The report `docs/eval/bandit-online.md` is written from it. If the rule says off, switch the bandit and the canary off as above.

## Export preference pairs

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=frc uv run poe export-preferences
uv run poe export-preferences --from data/processed/preferences/firestore --runs copilot-v2
```

The first reads the deployment's ratings and picks as the owner and keeps a copy; the second reads that copy and adds local runs' validator pairs. Both write `data/processed/preferences/pairs.jsonl` and `pairs-meta.jsonl` ([data card](../data/preference-pairs.md)). Nothing they write is committed.

## Costs

The bandit's calls and its judge's are billed by Cerebras, at most $0.25 a day; the canary alone should cost $0.05 to $0.08 a day at ten questions, and twice that at twenty. The nightly evaluation and the paid fallback spend from the same key under their own caps, so Cerebras's own console shows all three together.
