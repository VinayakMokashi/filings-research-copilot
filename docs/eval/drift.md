# Drift checks: the first look

Phase 9, step 9.5 ([ADR-0037](../decisions/0037-drift-checks.md), [guide](../concepts/online-evaluation.md#drift-checks)). Every night's and every canary day's history line carries the drift checks from 15 November. This report keeps their first numbers; the Phase 9 close adds the first comparisons with the default windows.

## Question

Has anything under the copilot moved since the first nights? Three signals each read one part:

- **retrieval similarity:** the collection and the search;
- **refusals:** the answering;
- **latency:** the live service.

## Setup

- **The tests,** as in ADR-0037:
  - retrieval similarity: paired per question, and as a distribution (the two-sample Kolmogorov-Smirnov statistic, with a p-value from relabelling);
  - refusals: paired per question;
  - the canary's latency: paired per question.

  Holm adjusts each source's tests together.
- **The windows:** the first three periods that recorded a signal against the last three, so each signal needs six periods.
- **The data:** the `eval-history` branch, read by `poe drift-check`, which makes no model calls.

## Results (15 November)

- **Too few periods yet for the default windows:**
  - five nights (11 to 15 November) record refusals;
  - similarity is recorded from the night of 16 November;
  - the canary's first scheduled day is 15 November.
- **A look with windows of two nights** (`poe drift-check --window 2`). Refusals were 0.109 in the first two nights and 0.109 in the last two. The comparison covers the 46 questions that both windows asked: difference 0.00, 95% interval −0.09 to 0.08, p = 1.0. No drift.

## Limits

- **Three periods see a step, not a creep.** A slow change shows in the trend instead.
- **The full night of 15 November answered 70 of its 100 questions,** so it adds only those 70 to the refusals.
- **The nightly run's latency isn't tested.** It is paced for the free tier, so latency is read from the canary, whose requests are live and unpaced.

## Next

- Retrieval similarity's first comparison after six recorded nights, about 21 November.
- The canary's latency and similarity after six canary days, about 20 November.
