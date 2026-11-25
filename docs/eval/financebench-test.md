# FinanceBench's held-out test split

Phase 10. FinanceBench test, 50 questions from 12 companies, held out since Phase 1 and opened once here, for the final copilot and the doc agent alone.

## Question

On the dev split, the copilot's version 2 answers 0.65 of the questions correctly, as many as the doc agent alone, with more figure questions right and far more faithful text answers ([report](copilot-v2.md)). But its routing rules and the validator's changes were written from its losses on those same dev questions. Does it hold on questions from companies it never saw while being built, and does it still match the doc agent alone there?

## Setup

- **The questions:** FinanceBench's 50 test questions, from 12 companies that are not in dev ([ADR-0006](../decisions/0006-evaluation-splits.md)): 16 domain-relevant, 17 metrics-generated and 17 novel-generated. The split's checksum was checked when it was opened, and the scripts refuse it unless a run asks for it by name (`--split test --allow-test`).
- **The systems,** as built at commit `fb4158f`; the agents are unchanged since, and Phase 10 touched only the web UI:
  - `copilot-v2`: the whole copilot as deployed, router prompt r2 and the validator's version 2 ([ADR-0026](../decisions/0026-copilot-v2.md));
  - `doc-agent-v4-cerebras`: the doc agent alone, the baseline the copilot was compared with on dev.
- **The models and data, the scheduled evaluation's** ([ADR-0034](../decisions/0034-nightly-evaluation.md)): gpt-oss-120b (`strong`) and Qwen3.8 27B (`fast`, reasoning off) on Cerebras; the validator's checker gpt-oss-20b (`small`) on Groq; the evaluation data bundle and Qdrant Cloud's collection, read-only.
- **The judges, the dev runs':** correctness by Qwen3.8 27B on Cerebras (rubric prompt 2, figures compared by code), faithfulness by prompt 1, so test and dev scores compare.
- **Before the validator:** each answer as its specialist first wrote it (`copilot-v2-drafts`), judged the same way, as on dev.
- **Budget:** a hard cap of $0.75 for every call of every step, approved by the owner and enforced by one ledger. The copilot ran in two halves on two days, so Groq's free daily quota for the small role still covered the nights' runs.
- **Tests:** paired permutation tests on the same 50 questions ([ADR-0007](../decisions/0007-evaluation-statistics.md)). Test against dev is not paired: different questions from different companies, so those comparisons use a two-sample permutation test.

## Results

### Correctness

| Outcome | Copilot | Copilot before the validator | Doc agent alone | Copilot on dev | Doc agent alone on dev |
|---|---|---|---|---|---|
| Correct | **0.68 (0.56 to 0.80)** | 0.70 (0.58 to 0.82) | 0.66 (0.52 to 0.78) | 0.65 (0.56 to 0.74) | 0.65 (0.55 to 0.74) |
| Incorrect | 0.26 | 0.30 | 0.30 | 0.26 | 0.28 |
| Refused or declined | 0.06 | 0.00 | 0.04 | 0.09 | 0.07 |

| Question type | Copilot | Before the validator | Doc agent alone |
|---|---|---|---|
| Metrics-generated (17) | **16** | 16 | 13 |
| Domain-relevant (16) | 10 | 10 | 10 |
| Novel-generated (17) | 8 | 9 | 10 |
| **All (50)** | **34** | 35 | 33 |

**On companies it never saw, the copilot does as well as on dev, and as well as the doc agent alone.** Its 0.68 is 0.03 above its dev score, and the doc agent's 0.66 is 0.01 above its own; neither difference can be told from chance. On the same 50 questions the copilot leads the doc agent alone by 0.02, which can't be told from none either (p = 1.00).

**The pattern of dev holds as well.** Against the doc agent alone, the copilot gains 4 questions and loses 3. All 4 gains are figure questions it answered through the data agent. Two of the 3 losses are novel-generated questions on the doc and hybrid routes, and one is a figure question the data agent got wrong where the doc agent, reading pages, was right.

### Where the questions went

| Question type | Data | Doc | Hybrid |
|---|---|---|---|
| Metrics-generated (17) | 17 | 0 | 0 |
| Domain-relevant (16) | 2 | 7 | 7 |
| Novel-generated (17) | 1 | 13 | 3 |
| **All (50)** | **20** | **20** | **10** |

Every figure question went to the data agent, as on dev, and no question was declined. The LLM router on gpt-oss-120b decided all 50, as it decided all 100 on dev, and its fallback was never needed. One question the data agent couldn't answer was handed on to the doc agent, which answered it correctly.

| Route | Questions | Copilot correct | Doc agent alone, same questions | On dev: copilot and doc agent alone |
|---|---|---|---|---|
| Data | 20 | **19** | 16 | 36 and 33, of 40 |
| Doc | 20 | 12 | 13 | 18 and 19, of 36 |
| Hybrid | 10 | 3 | 4 | 11 and 13, of 23 |

**The routes balance the same way on both splits:** the data agent wins three figure questions, and the doc and hybrid routes give one or two back against the doc agent alone. The hybrid questions are the hardest for both systems: the doc agent alone answers 4 of these 10.

### The validator

The validator checked the 31 answers from the doc and hybrid routes, the handed-on one included: 18 passed at once, 8 were revised once and 5 twice. 26 ended faithful by its check, 4 of them with a labelled assessment.

Against the drafts it changed 4 verdicts, all on revised answers: 3 wrong drafts ended as declines, and 1 right draft became wrong. The difference, −0.02 (−0.06 to +0.00), is within chance (p = 1.00), as on dev (−0.02, p = 0.50), where it also turned 2 wrong drafts into declines.

**One question needed more than one run.** Its revised answer's check came back unreadable twelve times over three runs: Groq refused the checker's reply as invalid JSON, at temperature 0, and a strict run stops so it can resume. A fourth run, with `--lenient`, would have let the answer pass unchecked, as the live API does. That run got a readable reply on a retry, so the answer was checked like the rest, and no answer went out unchecked.

### Faithfulness

As on dev, faithfulness is reported for the doc and hybrid answers, since the check can't read the data agent's answers, which cite the database as a whole. On the 27 answered doc and hybrid questions:

| | Copilot | Before the validator | Doc agent alone, same questions |
|---|---|---|---|
| Faithful: every sentence supported | **0.74 (0.56 to 0.89)** | 0.59 (0.41 to 0.78) | 0.56 (0.37 to 0.74) |
| Share of sentences supported | 0.89 | 0.79 | 0.75 |

The copilot's text answers are more faithful than the doc agent's here too, by less than on dev (0.82 against 0.49 there). With 27 answers the difference is +0.19 (+0.04 to +0.33), and the permutation test puts it at p = 0.06, short of the 0.05 the project's rule asks. Over all 47 answers, the data agent's included, the run scores 0.45 faithful; the doc agent alone scores 0.62 on its 48.

### Cost and time

$0.0047 a question at list prices ($0.24 for the 50), against $0.0050 on dev: 376,142 tokens on gpt-oss-120b, 65,323 on Qwen3.8 27B and 74,562 on gpt-oss-20b. 8.6 steps a question. The data route cost $0.0039 a question, the doc route $0.0047 and the hybrid $0.0063.

The times are paced for the free tier's limits, so they measure the run's throughput, not a visitor's wait: 19 s at the median and 87 s at the 95th percentile; the hybrid route's median was 50 s.

**The whole test split cost $0.44 of its $0.75 cap,** over 529 calls: both systems' answers, the drafts, the judge and the faithfulness checks.

## Comparison

Paired permutation tests on correctness, every run graded by the same judges:

| Comparison | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Copilot against the doc agent alone | 50 | +0.020 (−0.080 to +0.120) | 1.00 |
| — metrics-generated | 17 | +0.176 (−0.059 to +0.412) | 0.38 |
| — domain-relevant | 16 | +0.000 | 1.00 |
| — novel-generated | 17 | −0.118 (−0.294 to +0.000) | 0.49 |
| Copilot against its drafts (the validator) | 50 | −0.020 (−0.060 to +0.000) | 1.00 |
| Drafts against the doc agent alone (routing and the specialists) | 50 | +0.040 (−0.060 to +0.140) | 0.68 |

Test against dev, two-sample permutation tests:

| Comparison | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Copilot, test against dev | 50 and 100 | +0.030 (−0.130 to +0.190) | 0.86 |
| Doc agent alone, test against dev | 50 and 100 | +0.010 (−0.150 to +0.170) | 1.00 |

On the 27 doc and hybrid answers, faithfulness rises from the doc agent's 0.56 to 0.74 (+0.185, from +0.037 to +0.333; p = 0.06), and from the drafts' 0.59 (+0.148, from +0.037 to +0.296; p = 0.12).

## Decision

**No change: the copilot as deployed is the final version, and these are its held-out numbers** ([ADR-0026](../decisions/0026-copilot-v2.md)). The test confirms what dev showed, on companies the rules weren't written from:

- **Correctness carries over:** 0.68 on test against 0.65 on dev, level with the doc agent alone on both.
- **The gain is on figures.** The data agent answered 16 of the 17 figure questions, against 13 for the doc agent reading pages.
- **Analyst questions still cost a little.** On novel-generated questions the copilot trails the doc agent alone by two, within chance, as on dev.
- **Faithfulness holds in direction,** not in size: the validator lifts the text answers' faithfulness, by less on these 27 than on dev's 55.

The split is now spent. Nothing will be tuned on it, and later changes are measured on dev and in the scheduled evaluation.

**Limits:**

- **50 questions, one run of each system.** A few questions move each comparison, and the intervals are about ±0.13 wide.
- **The judges are models,** checked against reference labels from a stronger model, not a person ([ADR-0014](../decisions/0014-answer-judge.md)).
- **FinanceBench's questions are templated** and name their filing, so the test shows the copilot carries over to new companies, not to every question an analyst might ask.
- **The faithfulness check can't read data answers,** so it covers 27 of the 47 answers.

## Logs

- Runs (question ids, verdicts and metrics only), each in a `test/` folder: the agent metrics in [`eval/results/copilot/copilot-v2/test/`](../../eval/results/copilot/copilot-v2/test/); the doc agent's answer metrics in [`eval/results/answers/doc-agent-v4-cerebras/test/`](../../eval/results/answers/doc-agent-v4-cerebras/test/); correctness in [`eval/results/correctness/`](../../eval/results/correctness/) and faithfulness in [`eval/results/faithfulness/`](../../eval/results/faithfulness/), for `copilot-v2`, `copilot-v2-drafts` and `doc-agent-v4-cerebras`.
- The answers, the drafts and the copilot's trace stay local, in the evaluation data bundle's folder: FinanceBench's licence keeps answers to its questions out of the repository.
- Reproduce ([runbook](../runbooks/running-evaluations.md#run-the-copilot-end-to-end)) with the scheduled evaluation's settings (`FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b`, `FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b`, the data bundle and Qdrant Cloud's read-only key) and a run budget (`FRC_LLM_BUDGET_USD`, `FRC_LLM_BUDGET_FILE`). The test split is spent, so these are for checking the numbers, not for tuning:

  ```bash
  uv run poe run-copilot --run copilot-v2 --split test --allow-test
  uv run poe answer-questions --run doc-agent-v4-cerebras --split test --allow-test
  uv run poe judge-answers --run copilot-v2 --split test --allow-test
  uv run poe judge-answers --run copilot-v2-drafts --split test --allow-test
  uv run poe judge-answers --run doc-agent-v4-cerebras --split test --allow-test
  uv run poe check-faithfulness --run copilot-v2 --split test --allow-test
  uv run poe check-faithfulness --run copilot-v2-drafts --split test --allow-test
  uv run poe check-faithfulness --run doc-agent-v4-cerebras --split test --allow-test
  uv run poe compare-runs eval/results/correctness/doc-agent-v4-cerebras--qwen-3.8-27b-p2/test eval/results/correctness/copilot-v2--qwen-3.8-27b-p2/test --metric correct
  ```
