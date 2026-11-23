# ADR-0037: Check for drift where each signal is clean, and report it rather than alarm

- **Status:** Accepted
- **Date:** 2026-11-15
- **Phase:** 9

## Context

Step 9.5 asks for drift checks on retrieval scores, the refusal rate and latency. Drift is a change in how the running system behaves when nothing in its code says it should: a provider's update, a changed collection in Qdrant Cloud, a slower model or region. The regression tests of [ADR-0034](0034-nightly-evaluation.md) catch a drop in quality against a baseline. Drift checks watch the system's internals for movement before quality shows it.

The data available:

- **The nightly evaluation** asks the same questions every night, so any movement is the system's own, not the questions'. But its seconds are paced for the free tier's limits (ADR-0034's report says so), and they measure throughput, not a reader's wait.
- **The daily canary** ([ADR-0036](0036-bandit-online.md)) asks the live API ten of the routing set's questions a day, unpaced, so each question comes round every three days (twenty a day on the weekdays of 16 to 20 November).
- **Visitors' traffic** was 3 questions in twelve days, too thin for daily aggregates.
- **No retrieval score was recorded** anywhere; the nightly rows held correctness, faithfulness, cost and seconds.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Daily aggregates of the API's own traffic | What visitors really see | Almost no traffic |
| Everything from the nightly evaluation | One source, same questions every night | Its latency is the pacing's, not the API's |
| **Each signal from where it is clean** | Similarity and refusals on fixed questions; latency from live, unpaced requests | Two sources to read |
| Alarm on drift (fail the run, open an issue) | Nothing goes unnoticed | Windows of three nights are small, so alarms would be mostly noise; regressions already alarm |

## Decision

1. **Record retrieval similarity:** the cosine similarity between a question and the best chunk its own search finds. The first search is always the question itself, so this is stable for a fixed question.
   - It comes from the first retrieval, so a retry's wider search doesn't add noise.
   - It travels from the doc agent and the hybrid through the graph's `answer` event and result, to local runs' records and the nightly rows; the canary reads it from the live API's events.
2. **Three checks** (`copilot.eval.drift`):

   | Signal | Source | Test |
   |---|---|---|
   | Retrieval similarity | The nightly run, and the canary | Per question, paired permutation test; and as a distribution, the two-sample Kolmogorov-Smirnov statistic with a permutation p-value |
   | Refusals | The nightly run | Each question's share of nights unanswered, paired permutation test |
   | Latency | The canary | Each question's first time against its latest, paired permutation test |

3. **Windows.** For each signal, the first three nights (or days) that recorded it are the reference, and the last three the recent period. With fewer than six, it isn't compared yet. The tests of a source are Holm-adjusted together, and a drift is an adjusted p-value below 0.05.
4. **Reported, not alarmed.** Each night's and each canary day's history line carries its drift checks, and `poe drift-check` shows them for any window. A failure inside the checks is recorded as an error and never costs the night or the day its metrics.

## Evidence

The first look, on 15 November ([report](../eval/drift.md)). Five nights had recorded refusals, and windows of two nights found them unchanged: 0.109 and 0.109 on 46 questions, p = 1.0. Retrieval similarity is recorded from the night of 16 November and the canary's days from 15 November, so the default windows of three compare from about 20 November.

The first comparisons with the default windows, on 23 November (13 nights, 8 canary days; [report](../eval/drift.md#results-23-november-the-default-windows)), found no drift:

- the nightly's retrieval similarity, 0.7308 against 0.7339 on 20 questions (16 to 18 against 21 to 23 November), and its distribution (KS 0.05);
- the nightly's refusals, 0.114 against 0.085 on 51 questions (11 to 13 against 21 to 23 November);
- the canary's latency, 14.9 s against 14.6 s on 20 questions, and its similarity, unchanged to the fourth decimal (15 to 17 against 20 to 22 November).

Every adjusted p-value was 1.0.

## Consequences

- **The first comparisons need six periods each:** similarity from the night after this change is deployed, refusals at once (the history holds four nights), latency from the canary's sixth day.
- **The reference is fixed at the start.** A deliberate change (a new collection, a model swap) will read as drift ever after. The fix is to start a new reference by hand, and the check then says what changed and when.
- **Small windows see only large drifts.** Three nights of 32 questions show a step change, such as a re-indexed collection, not a slow creep. The trend on the project page is where a creep would show.
- **The API's `answer` events gain a number,** the similarity, which the UI ignores.

## References

- Rabanser, Günnemann and Lipton, [Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift](https://arxiv.org/abs/1810.11953), NeurIPS 2019 (two-sample tests for shift).
- Breck et al., [The ML Test Score](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/), 2017 (monitoring tests).
- [ADR-0007](0007-evaluation-statistics.md) (permutation tests, Holm), [ADR-0034](0034-nightly-evaluation.md), [ADR-0036](0036-bandit-online.md).
