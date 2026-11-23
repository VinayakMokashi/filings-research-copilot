# Drift checks: the first look and the first comparisons

Phase 9, step 9.5 ([ADR-0037](../decisions/0037-drift-checks.md), [guide](../concepts/online-evaluation.md#drift-checks)). Every night's and every canary day's history line carries the drift checks from 15 November. This report keeps their first numbers, and the first comparisons with the default windows on 23 November.

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

## Results (23 November): the default windows

By 23 November the history held 13 nights and 8 canary days, enough for every signal's windows of three (`poe drift-check`). Each value is the mean over the questions both windows asked, of each question's mean in its window.

| Source | Signal | Reference | Recent | Questions | Reference value | Recent value | Difference (95% interval) | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| Nightly | Retrieval similarity | 16 to 18 Nov | 21 to 23 Nov | 20 | 0.7308 | 0.7339 | +0.003 (−0.001 to +0.011) | 1.0 |
| Nightly | Similarity, as a distribution | 16 to 18 Nov | 21 to 23 Nov | | | | KS 0.05 | 1.0 |
| Nightly | Refusals | 11 to 13 Nov | 21 to 23 Nov | 51 | 0.114 | 0.085 | −0.029 (−0.092 to +0.033) | 1.0 |
| Canary | Latency, seconds | 15 to 17 Nov | 20 to 22 Nov | 20 | 14.92 | 14.59 | −0.33 (−4.08 to +2.08) | 1.0 |
| Canary | Retrieval similarity | 15 to 17 Nov | 20 to 22 Nov | 20 | 0.7508 | 0.7508 | 0.000 | 1.0 |

- **No drift.** Nothing moved beyond what the intervals allow, before or after Holm's adjustment.
- **The canary's similarity didn't move at all.** The canary asks the same questions of the same collection, all on the doc route, whose first search is the question's own, so a question's similarity changes only if the collection or the search does. That is the point of the signal: any change there would be the system's.
- **The nightly's similarity moved by 0.003, inside the interval.** Most of its questions repeat their similarity to the fourth decimal from night to night. A few don't: on the hybrid route the search runs on a part of the question that a model writes afresh each night, and the router sometimes sends a question down another route. Two hybrid questions varied by up to 0.08 between the nights of 16 to 23 November.
- **Refusals fell from 0.114 to 0.085,** within the interval.

## Limits

- **Three periods see a step, not a creep.** A slow change shows in the trend instead.
- **The full night of 15 November answered 70 of its 100 questions,** so it adds only those 70 to the refusals.
- **The nightly run's latency isn't tested.** It is paced for the free tier, so latency is read from the canary, whose requests are live and unpaced.
- **The canary's latency reference holds a cold start.** 16 November's questions were asked at 00:18 IST, and the first took 77 s, so that question's reference mean is high. The check still found no drift, and a slower service would show on all twenty questions, not one.
- **No alarm.** A drift is recorded in the history line, not raised as an issue: windows of three periods are small, so alarms would be mostly noise, and regressions already alarm ([ADR-0037](../decisions/0037-drift-checks.md)).

## Next

The checks go on with every night and every canary day, against the same reference windows. After a deliberate change, such as a new collection, the reference must be started again by hand, or the change will read as drift ever after.

**A change to note:** on 23 November, after these comparisons, onnxruntime moved from 1.31.1 to 1.32.0 in the deployment (10:08 UTC) and in the nightly runs (#135). It computes the query embeddings, so retrieval similarity may shift slightly from that day. Such a shift is the library's, not the collection's.
