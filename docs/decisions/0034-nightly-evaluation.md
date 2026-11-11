# ADR-0034: Evaluate the copilot every night in GitHub Actions, on Cerebras, within a hard cap

- **Status:** Accepted
- **Date:** 2026-11-11
- **Phase:** 9

## Context

Every quality number so far comes from a run made once, when a phase changed the copilot. The deployment has been live since 2 November, and its answers can get worse with nothing in this repository changing: a provider can update a model or its defaults (ADR-0024 found one such default), Qdrant Cloud's collection can change, and a merged change can regress a route that its own PR didn't measure. Phase 9 asks for a nightly evaluation with regression alerts and a trend chart.

The constraints:

- **Cost.** A copilot answer costs about $0.005 on Cerebras (copilot v2's dev run), and its judges add about a fifth to that. Groq's free tier allows about 200,000 tokens a day for each model, which a 100-question run uses up, and its quota is what visitors' answers run on.
- **The licence.** FinanceBench is CC BY-NC 4.0, so its questions, its answers and the copilot's answers to them are never published. The repository and its Actions artifacts are public.
- **No keys.** Deploys already reach Google Cloud through workload identity federation, limited to this repository's `main` (ADR-0032).

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **GitHub Actions on a schedule** | Free minutes for a public repository; keyless through the existing identity pool; the same commit as `main` | The data bundle and the questions must be fetched each night; a run is limited to six hours |
| The laptop, on a schedule | The data and the caches are already there | Not always on; a CPU-only machine that also runs other work |
| A Cloud Run job | Next to the deployment | New compute to pay for, and a second image to build |
| Only during demo windows | Nothing new runs | Too rare to show a trend |
| Groq's free tier as the provider | Free | Shares the visitors' daily quota; a 100-question run took three days in Phase 3 |
| **Cerebras, in Phase 7's evaluation setup** | Hours, not days; the same instrument as copilot v2's dev results (0.65 correct); the visitors' quota stays theirs | Paid, outside Google's budget |

## Decision

1. **Where.** A GitHub Actions workflow runs every night at 20:30 UTC (02:00 IST), from source with uv, so no image is pulled from the registry. It authenticates through workload identity federation as a new `eval` service account, which may read the data bundle and four secrets only: the Groq and Cerebras keys, and Qdrant Cloud's address and read-only key.
2. **What.** Each night:
   - the copilot answers a fixed slice of 40 FinanceBench dev questions, stratified by route and question type;
   - the LLM router decides the routing set's 138 dev questions;
   - the data agent answers the SQL set's 28 dev questions.

   The run that starts at 02:00 IST on a Sunday answers all 100 dev questions instead. The test split stays closed.
3. **How it is graded.** As in Phase 7: the strong and fast roles run on Cerebras and the small role on Groq (ADR-0024). The correctness judge (prompt 2) and the faithfulness check (prompt 1) run on Cerebras's Qwen with reasoning off. No cache carries over from one night to the next, so every night's calls are fresh.
4. **A hard cap.** At most $0.40 a night and $1.20 on Sundays, about $15 a month, enforced by the run itself.
   - The gateway counts each call's cost in a ledger the night's steps share, and refuses calls once the total reaches the cap.
   - Each step has its own share of the cap, so a run cut short still grades what it answered.
   - A run stopped by the cap is recorded as partial and draws no verdict.
   - The slice's size comes from one measured run: if a night costs more than the cap allows, the slice shrinks and the cap stays.
5. **Metrics only.** Each night stores ids, scores, categories, costs and times, never question or answer text.
   - It writes to the branch `eval-history`: a line per night in `nightly/history.jsonl`, and the per-question scores in `nightly/runs/`.
   - The project page draws the trend from that branch, with the month's Cerebras spend.
6. **Regressions.** Each metric is compared with the last full run on the same questions, by a paired permutation test, with the night's tests adjusted together (Holm, α = 0.05). The metrics are correct and answered on the slice, and the routing and SQL accuracies.
   - A significant drop fails the run and opens a GitHub issue, or comments on the one already open.

## Evidence

The sizing estimate, from copilot v2's dev run on Cerebras ([report](../eval/copilot-v2.md)):

| Step | Estimate a night |
|---|---|
| 40 answers at about $0.005 | about $0.20 |
| The judge and the faithfulness check | about $0.07 |
| The routing set's 138 decisions | about $0.10 |
| The SQL set's 28 answers | about $0.04 |
| **Total** | **about $0.40** |

That is at the cap, so the first run is made by hand and measured before the schedule starts. Its numbers will be added here.

## Consequences

- **Quality becomes a time series.** A drop shows within a day of its cause, with the commit that was on `main` that night.
- **The month's model spend** is at most about $15 at Cerebras's prices, and nothing on Google Cloud: the secrets are read a few times a night, within Secret Manager's free operations.
- **A 40-question slice detects only large drops.** With 40 paired questions and the night's tests adjusted together, a fall needs to be roughly 15 to 20 points to be significant; the Sunday run's 100 questions see smaller ones. The trend shows the rest.
- **Fresh calls vary.** Temperature 0 doesn't make every reply identical, so a night can differ from the last with nothing changed. The family-wise test keeps false alarms to about one night in twenty.
- **The small role uses Groq's free tier** in the rolling 24 hours visitors share, a few dozen checks a night, at the quietest hour.
- **The bundle and the questions are downloaded each night,** from the project's own bucket and FinanceBench's repository. The bundle is cached by its checksum.

## References

- [ADR-0007](0007-evaluation-statistics.md): the paired permutation test and the intervals.
- [ADR-0024](0024-second-provider.md): Cerebras for the strong and fast roles, and its defaults.
- [ADR-0032](0032-continuous-deployment.md): workload identity federation from GitHub Actions.
- [ADR-0033](0033-capped-paid-fallback.md): the cap's accounting, which this one follows.
- Holm, A Simple Sequentially Rejective Multiple Test Procedure, *Scandinavian Journal of Statistics* 6(2), 1979.
- GitHub, [Events that trigger workflows: schedule](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule).
