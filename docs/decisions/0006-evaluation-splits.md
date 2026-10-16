# ADR-0006: Split FinanceBench by company into dev and held-out test

- **Status:** Accepted
- **Date:** 2026-10-17
- **Phase:** 1

## Context

FinanceBench's open-source sample has 150 questions about 32 companies. Phases 2 to 5 tune retrieval, prompts and routing against it, and Phase 7 fine-tunes an embedder on filing text. An honest result needs questions that played no part in any of that.

Two things make this hard. The set is small, and most companies appear in several questions and several filings, whose text barely changes from one year to the next.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Random 100/50 split | Simple | Question types can end up unbalanced, and a company's filings sit on both sides |
| Stratified by question type only | Balanced types | A company still sits on both sides, so tuning and Phase 7 training see test companies' filings |
| Grouped by document | No document on both sides | A test company's other years stay on the dev side, and their text is nearly identical |
| **Grouped by company, stratified by question type, seed chosen by a fixed search** | No test company is seen in tuning or training; question types balance exactly; reproducible | Sector shares are only approximate, and the scoring rule needs explaining |
| k-fold cross-validation | Every question is tested once | Each fold needs a full pipeline run, and nothing stays untouched for milestone claims |
| All 150 as test, tuning on synthetic questions | The largest test set | No real questions to tune on, and synthetic questions read differently from analysts' |

## Decision

Split by company into dev (100 questions) and test (50). The script tries seeds 0 to 19,999. For each seed it shuffles the companies, adds them to the test side until that holds at least 50 questions, and scores the result:

- 3 points for each question the test side is away from 50;
- 1 point for each question of deviation from a proportional mix of question types;
- ¼ point for each question of deviation from a proportional mix of document types, and the same for sectors;
- 5 points for each sector with more than one company that lands entirely on one side.

The lowest score wins, and ties go to the earlier seed. Scores are exact fractions, so floating-point rounding can't change the result. Seed 14,793 won with a score of 8.33.

The test side is held out. `load_split("test", ...)` raises an error unless it is called with `allow_test=True`, which only milestone evaluations use, and every eval report states whether the test set was opened. Both sides are checked against the SHA-256 checksums in `eval/financebench/splits.json` whenever they load. Phase 7 trains only on filings from companies with no test questions.

## Evidence

From the [data card](../data/financebench.md#splits):

- Question types: 33 / 34 / 33 in dev and 17 / 16 / 17 in test.
- Document types (10-K / 10-Q / 8-K / earnings): 74 / 12 / 6 / 8 percent in dev and 76 / 6 / 6 / 12 percent in test, against 75 / 10 / 6 / 9 percent overall.
- All eight sectors with more than one company appear on both sides.

## Consequences

- The test set gives one honest number per milestone, but with wide intervals: about ±14 points near 50% accuracy. Day-to-day decisions use paired tests on dev.
- Sector shares differ between the sides. Information technology is 28% of test questions and 8% of dev; financials are 2% of test and 12% of dev. Results are also broken down by sector when that matters.
- 12 of the 16 test domain-relevant questions share a template with a dev question. The templates are generic analyst questions, so this is accepted, and results are reported by question type as well.
- Changing the split would void the held-out set. The script refuses to replace the split file without `--force`, and any replacement needs a new ADR.

## References

- Islam et al., *FinanceBench: A New Benchmark for Financial Question Answering* (2023), arXiv:2311.11944.
- Kapoor and Narayanan, "Leakage and the reproducibility crisis in machine-learning-based science", *Patterns* 4(9), 2023.
- scikit-learn's `StratifiedGroupKFold`, which applies the same idea (groups kept whole, strata balanced) to cross-validation.
