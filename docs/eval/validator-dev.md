# The validator loop: dev evaluation

Phase 5, step 5.3. FinanceBench dev, 100 questions; the held-out test split was not opened.

## Question

The doc agent cites a source for every sentence, but 35 of the 94 answers it gave to FinanceBench dev questions had a sentence its citations didn't support ([report](doc-agent-dev.md)). Does checking every cited sentence before an answer is shown, and sending what fails back to the writer at most twice, make answers faithful without costing correctness, and what does it cost?

## Setup

- **Answers:** the doc agent's stored answers to the 100 dev questions (`doc-agent-v4-full`, Phase 3): 94 answers and 6 refusals. `poe validate-answers` runs each through the loop as the graph's `validate` and `revise` nodes do, so the comparison is paired: the same questions and the same first answers ([guide](../concepts/validator-loop.md)).
- **Checker:** gpt-oss-20b, the `small` role, with the faithfulness check of Phase 3 (`copilot.eval.faithfulness`): each sentence against the sources it cites.
- **Writer:** gpt-oss-120b, the `strong` role, the doc agent's own model and rules, given the same sources and the failing sentences.
- **Stopping:** at most two revisions; then the answer keeps its verified sentences, or becomes a refusal that says what couldn't be verified.
- **Graded** by the judges of Phase 3, both Qwen3.8 27B: correctness (rubric prompt 2, figures compared by code) and faithfulness (prompt 1) ([ADR-0014](../decisions/0014-answer-judge.md)). The checker is a different model from both, so the loop can't learn to please its grader.
- **Tests:** paired permutation tests ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

| | Doc agent (Phase 3) | Validated |
|---|---|---|
| Correct | 0.65 (0.56 to 0.74) | 0.61 (0.51 to 0.71) |
| Incorrect | 0.29 | 0.31 |
| Refused | 0.06 | 0.08 |
| Answers (not refusals) | 94 | 92 |
| Faithful: every sentence supported by its citations | 0.628 (0.532 to 0.723) | 0.848 (0.772 to 0.924) |
| Share of sentences supported | 0.771 (0.698 to 0.840) | 0.906 (0.849 to 0.955) |

**What the loop did** with the 94 answers it checked:

- **66 passed the first check** and were shown as written.
- **28 were revised,** 17 once and 11 twice; 21 of them then passed.
- **7 still failed after two revisions:** 5 kept only their verified sentences, one lost all of them and became a refusal, and in one the revision itself declined.

**Against the judge's verdicts on the first answers:** of the 35 answers the faithfulness judge had found unfaithful, the checker revised 25 and passed 10; of the 59 it had found faithful, the checker revised 3. After the loop, 19 answers went from unfaithful to faithful and none the other way.

**By question type:**

| Question type | Correct, before → after | Faithful, before → after |
|---|---|---|
| Domain-relevant (34) | 0.588 → 0.441 | 0.406 → 0.781 |
| Metrics-generated (33) | 0.879 → 0.879 | 0.871 → 0.967 |
| Novel-generated (33) | 0.485 → 0.515 | 0.613 → 0.800 |

**Every change in correctness came from a revised answer:** 5 went from correct to incorrect, 2 from incorrect to correct, one correct answer and one incorrect one became refusals.

- **All five losses are domain-relevant questions,** which ask for an analyst's judgement about a company's figures. In two, the first answer's judgement rested on a general benchmark or an industry norm; the checker failed that sentence, the revision dropped it, and the judge marked both answers incorrect. In a third, the revision dropped a percentage the model had worked out itself, which was right, and kept the calculator's, which was formatted as a fraction of one per cent. In a fourth, the revision added figures that the judge found more than 1% from the reference. The fifth answer covered the same years before and after, and its verdict changed anyway: judge noise on a borderline answer.
- **The two gains** are novel-generated questions: a revision corrected the sign of an effective tax rate, and another added the figures that showed which segment was lowest.
- **The new refusals:** one answer lost every sentence after two failed revisions. The other was correct, but its only sentence wasn't supported by the page it cited, as the faithfulness judge had also found, and the revision declined rather than answer without support.

**Cost**, at list prices, for the 100 answers:

| | Tokens in / out | Cost |
|---|---|---|
| Checks, gpt-oss-20b | 161,703 / 68,600 | $0.033 |
| Revisions, gpt-oss-120b | 169,568 / 36,269 | $0.047 |
| **Total** | | **$0.080, or $0.0008 an answer** |

The doc agent's answer costs $0.0011, so the loop adds about 70%, most of it on the 28 revised answers ($0.0017 each in revisions).

## Comparison

Paired permutation tests against the doc agent's first answers:

| Measure | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Faithful | 92 answered both times | +0.207 (+0.130 to +0.293) | 0.0001 |
| Share of sentences supported | 92 answered both times | +0.118 (+0.070 to +0.173) | 0.0001 |
| Correct | 100 | -0.040 (-0.100 to +0.010) | 0.28 |
| Correct, domain-relevant | 34 | -0.147 (-0.265 to -0.029) | 0.063 |
| Correct, metrics-generated | 33 | 0.000 | 1.00 |
| Correct, novel-generated | 33 | +0.030 (-0.061 to +0.121) | 1.00 |

Faithfulness rises by 21 points, far beyond chance. Correctness falls by 4 points overall, which a paired test can't tell from noise; on the domain-relevant questions it falls by 15 points, at the edge of significance (the bootstrap interval excludes zero; the permutation test's p is 0.063).

## Decision

Adopt the loop in the copilot ([ADR-0019](../decisions/0019-validator-loop.md)):

- **It keeps the copilot's own rule.** Every sentence must be supported by the sources it cites; the loop enforces that rule, which the doc agent alone kept in 63% of its answers, in 85%, and it turned no faithful answer unfaithful.
- **Figure questions are untouched:** the metrics-generated questions keep their correctness, 0.879, and gain faithfulness.
- **The price is judgement.** Domain-relevant questions reward an analyst's judgement drawn from general knowledge (a usual benchmark, an industry norm), which the copilot's rules already forbid and the loop now removes. Letting an answer give such an assessment, labelled as its own and separate from the cited facts, is an open question for a later phase.
- **The checker misses some:** it passed 10 of the 35 answers the judge found unfaithful, so a checked answer is likelier to be faithful, not certain to be.

## Logs

- Runs: [`eval/results/correctness/doc-agent-v4-validated--qwen3.8-27b-p2/dev/`](../../eval/results/correctness/doc-agent-v4-validated--qwen3.8-27b-p2/dev/) and [`eval/results/faithfulness/doc-agent-v4-validated--qwen3.8-27b-f1/dev/`](../../eval/results/faithfulness/doc-agent-v4-validated--qwen3.8-27b-f1/dev/): question ids, verdicts and metrics only.
- The validated answers, with each check's verdict, the revisions and the tokens: `data/processed/answers/doc-agent-v4-validated/dev/answers.jsonl` (local: FinanceBench's licence keeps answers to its questions out of the repository).
- Reproduce ([runbook](../runbooks/running-evaluations.md)):

  ```bash
  uv run poe validate-answers --source doc-agent-v4-full --run doc-agent-v4-validated
  uv run poe check-faithfulness --run doc-agent-v4-validated
  uv run poe judge-answers --run doc-agent-v4-validated
  uv run poe compare-runs eval/results/correctness/doc-agent-v4-full--qwen3.8-27b-p2/dev eval/results/correctness/doc-agent-v4-validated--qwen3.8-27b-p2/dev --metric correct --where question_type=domain-relevant
  ```
