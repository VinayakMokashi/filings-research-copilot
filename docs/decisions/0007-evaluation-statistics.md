# ADR-0007: Report bootstrap intervals and decide with paired permutation tests

- **Status:** Accepted
- **Date:** 2026-10-17
- **Phase:** 1

## Context

Phases 2 to 7 make dozens of comparisons: chunkers, retrievers, rerankers, prompts, routers and fine-tuned models, each against the current baseline. The evaluation sets are small (100 dev and 50 test questions for FinanceBench), and the metrics come in different shapes: 0/1 outcomes (correct, executes, routed right), graded scores (recall@k) and reciprocal ranks. The plan needs one rule for when a change ships, and one way to report uncertainty that works for every metric.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Point estimates only | Simple | Hides the noise; on small sets it misleads |
| Normal-approximation intervals and paired t-tests | Closed form, fast | Poor near 0 or 1 and at small n; assumes the mean is normally distributed |
| Wilson intervals | Good coverage for proportions | Only for 0/1 metrics, not recall or reciprocal rank |
| **Percentile bootstrap intervals and a paired permutation test** | One method for every metric; no distribution assumptions; standard practice in NLP evaluation | Monte Carlo noise, controlled by seeds and 10,000 resamples; percentile intervals run slightly narrow at small n |
| BCa bootstrap intervals | Better coverage for skewed statistics | More machinery, little gain for means of bounded scores |
| Paired bootstrap test | Common in machine translation | Its p-values rest on a shifted resampling distribution and are less exact under the null hypothesis than a permutation test |

## Decision

- Every reported metric is a mean with a 95% percentile bootstrap interval (10,000 resamples, seed 0).
- Comparisons pair questions by id. They report the mean difference with its bootstrap interval, and a two-sided p-value from a paired permutation (sign-flip) test with 10,000 flips, computed as (count + 1) / (10,000 + 1).
- A change ships when it improves the metric on dev with p < 0.05. When one experiment compares several variants with the same baseline, the p-values are Holm–Bonferroni adjusted first.
- For 0/1 metrics, McNemar's exact test is reported alongside as a cross-check.
- Test-set results are reported with intervals at milestones, and nothing is tuned on them ([ADR-0006](0006-evaluation-splits.md)).

## Evidence

- The unit tests in `tests/test_stats.py`: for a 0/1 metric at n = 50, the bootstrap interval matches the normal approximation within 15%; identical systems give p = 1; McNemar and Holm match hand-computed values.
- The first real run, the first-pages baseline on FinanceBench dev: hit@20 = 0.29 (95% interval 0.20 to 0.38).

## Consequences

- Given the same per-question scores, every interval and p-value is reproducible exactly.
- Small effects can't be confirmed on dev. If two systems disagree on 10 questions, a 7 to 3 split isn't significant (McNemar p = 0.34), while 9 to 1 is (p = 0.021). Experiments need sizeable gains, or more questions.
- numpy becomes a runtime dependency; Phase 2 needs it for embeddings anyway.
- One method across all metrics keeps reports comparable from phase to phase.

## References

- Efron and Tibshirani, *An Introduction to the Bootstrap* (1993).
- Dror et al., "The Hitchhiker's Guide to Testing Statistical Significance in Natural Language Processing", ACL 2018.
- Berg-Kirkpatrick et al., "An Empirical Investigation of Statistical Significance in NLP", EMNLP 2012.
- Holm, "A Simple Sequentially Rejective Multiple Test Procedure", *Scandinavian Journal of Statistics* (1979).
