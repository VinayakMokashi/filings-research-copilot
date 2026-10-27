# The copilot's version 2: dev evaluation

Phase 7, step 7.7. FinanceBench dev, 100 questions; the held-out test split was not opened.

## Question

The copilot's first version answered fewer dev questions correctly than the doc agent alone (0.49 against 0.65; [report](copilot-dev.md)). Of the 19 questions it lost, 10 went to the data agent, which declined them or computed the wrong figure, and 6 were right as first drafted but lost in the validator's revisions. Do four changes aimed at those losses win them back, without losing the figure questions the data agent answers?

## What changed

Each change is aimed at a loss the first version's run recorded; none adds a model or a prompt for the answers themselves.

| Change | Where | Aimed at |
|---|---|---|
| **Hand a question on.** When the data agent declines, fails, or its query returns no rows, the doc agent answers the question instead. | the graph (`after_data`) | 7 data-route losses: 5 declines ("the database doesn't store segments") and 2 queries that returned no rows |
| **Route by the database's grain.** Router prompt r2 adds two rules: the database holds annual figures for whole companies, so a question about a quarter, a segment, a product line or a region, or about a figure that isn't one of its measures, is doc (or hybrid); and a question that asks for an assessment of reported figures is hybrid, not investment advice. | the router (`GRAIN_RULES`) | 3 data-route losses where the data agent computed the wrong figure, and the one question declined as advice |
| **Keep a labelled assessment.** A sentence that begins "Assessment:" is the answer's own reading of the facts it cites: the check doesn't fail the answer for it, and trimming keeps it beside a verified fact. The revision prompt says so. | the validator (version 2) | answers whose verdict the revisions dropped |
| **Revise without losing the answer.** The revision prompt asks for every figure to be computed again, with a percentage's expression multiplying by 100; a revision that turns an answer into a refusal is set aside, and the answer is cut to its verified sentences instead. | the validator and the graph | two revisions that wrote a margin of 33% as "0.33%", and one that refused |

The rules were written from the first version's losses on these same dev questions, so this run measures how much of the loss they recover, not how they generalise: the test split stays closed until the copilot is final. Router r2 was also checked on the routing set's dev questions, which it was not written from.

## Setup

- **Questions, models and judges** as for the first version: the copilot on Cerebras (gpt-oss-120b `strong`, Qwen3.8 27B `fast` with reasoning off), the validator's checker gpt-oss-20b on Groq; correctness by Qwen3.8 27B on Cerebras (rubric prompt 2, figures compared by code) and faithfulness by prompt 1 ([ADR-0024](../decisions/0024-second-provider.md)).
- **Baselines:** `copilot-v1` and the doc agent alone on Cerebras (`doc-agent-v4-cerebras`), graded by the same judges.
- **Before the validator:** each answer as the specialist first wrote it (`copilot-v2-drafts`), as for version 1.
- **Tests:** paired permutation tests ([ADR-0007](../decisions/0007-evaluation-statistics.md)).
- **The routing set:** router r2 on its 138 dev questions, on Cerebras, against r1's 138 of 138 there.

## Results

### Correctness

| Outcome | Copilot v2 | v2 before the validator | Copilot v1 | Doc agent alone, on Cerebras |
|---|---|---|---|---|
| Correct | **0.65 (0.56 to 0.74)** | 0.67 (0.58 to 0.76) | 0.49 (0.39 to 0.59) | 0.65 (0.55 to 0.74) |
| Incorrect | 0.26 | 0.26 | 0.33 | 0.28 |
| Refused or declined | 0.09 | 0.07 | 0.18 | 0.07 |

| Question type | Copilot v2 | Copilot v1 | Doc agent alone |
|---|---|---|---|
| Metrics-generated (33) | **32** | 31 | 29 |
| Domain-relevant (34) | 16 | 8 | 19 |
| Novel-generated (33) | 17 | 10 | 17 |
| **All (100)** | **65** | 49 | 65 |

**Version 2 answers as many dev questions correctly as the doc agent alone, and keeps the data agent's lead on figure questions.** Against version 1 it gains 17 questions and loses 1. Of the 19 questions version 1 lost to the doc agent, 16 come back:

| What won the question back | Questions | How |
|---|---|---|
| Router r2 | 8 | 3 questions about a quarter or a one-off item now go to the doc agent; 3 about a region or asking for an assessment of a trend go to the hybrid; an assessment of growth, declined as investment advice before, goes to the hybrid; and one question moved the other way, to the data agent, which answered it |
| The validator's version 2 | 5 | 2 verdicts kept as labelled assessments; 2 margins computed as percentages again, where a revision had written 33% as "0.33%"; 1 revision that refused, set aside for the answer's verified sentences |
| The handoff | 4 | 3 questions the data agent declined (cash flows by activity, an effective tax rate) and 1 whose query returned no rows, answered by the doc agent |

The one question lost against version 1 was right as drafted in both versions; this time a revision trimmed a qualifying sentence the reference wanted. Against the doc agent alone, version 2 gains 4 (three figure questions the data agent answers, and one question the router r2 sent to it) and loses 4: two answers both versions drafted wrongly (a debt figure the data agent read as long-term debt only, and a margin history), and two the validator's revisions cost.

### Where the questions went

| Question type | Data | Doc | Hybrid | Decline |
|---|---|---|---|---|
| Metrics-generated (33) | 33 | 0 | 0 | 0 |
| Domain-relevant (34) | 5 | 11 | 18 | 0 |
| Novel-generated (33) | 2 | 25 | 5 | 1 |
| **All (100)** | **40** | **36** | **23** | **1** |

Router r2 moved 10 questions: 8 off the data route (5 to the doc agent, 3 to the hybrid), one from decline to the hybrid, and one from the doc agent to the data agent. Every figure question still goes to the data agent. The one question still declined asks what shareholders would receive in a hypothetical bankruptcy, which the router reads as speculation, as before.

**On the routing set, router r2 routes all 138 dev questions correctly,** as r1 did: the new rules changed no routing-set decision.

### The handoff

4 of the 40 questions on the data route were handed on: 3 the data agent declined and 1 whose query returned no rows. The doc agent answered all 4 correctly. Every question on the data route now gets an answer (40 of 40, against 40 of 47 in version 1, with seven declines).

### The validator

The validator checked 57 answers from the doc and hybrid paths: 29 passed first, 19 were revised once and 9 twice, and 51 ended faithful by its check; 6 were trimmed to their verified sentences, and none ended as a refusal. Against the drafts, it changed 4 verdicts: 2 right answers became wrong and 2 wrong ones became refusals (version 1: 6 right answers lost, 2 wrong ones refused). The difference from the drafts, −0.02, is within chance (p = 0.50); version 1's validator cost −0.06 (p = 0.03).

18 final answers keep a labelled assessment, written in a revision; 9 of them are correct. The faithfulness check grades an assessment like any other sentence, against the pages it cites, and 3 of the 18 answers fail it on that sentence.

### Faithfulness

As for version 1, faithfulness is reported for the doc and hybrid answers, since the check can't read the data agent's answers, which cite the database as a whole. On the 55 answered doc and hybrid questions:

| | Copilot v2 | v2 before the validator | Doc agent alone, same questions |
|---|---|---|---|
| Faithful: every sentence supported | **0.82 (0.71 to 0.91)** | 0.53 (0.40 to 0.65) | 0.49 (0.36 to 0.62) |
| Share of sentences supported | 0.89 | 0.75 | 0.73 |

The labelled assessments count as sentences here, so the check is strict with them: an assessment that goes beyond its pages fails the answer. Over all 91 answers, the data agent's included, the run scores 0.50 faithful.

### Cost

$0.0050 a question at list prices ($0.50 for the run): 793,428 tokens on gpt-oss-120b, 130,613 on Qwen3.8 27B and 173,821 on gpt-oss-20b. Version 1 cost $0.0047. The handoff adds the doc agent's cost to the questions it hands on, and the extra revisions add the writer's. 8.8 steps a question, against 8.7.

The run's times aren't comparable with version 1's: every model call whose prompt was unchanged replayed from the cache, so most of the data route took 3 to 4 seconds instead of 18.

## Comparison

Paired permutation tests on correctness, every run graded by the same judges:

| Comparison | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Version 2 against version 1 | 100 | +0.160 (+0.090 to +0.240) | 0.0002 |
| — domain-relevant | 34 | +0.235 (+0.088 to +0.412) | 0.024 |
| — metrics-generated | 33 | +0.030 (+0.000 to +0.091) | 1.00 |
| — novel-generated | 33 | +0.212 (+0.091 to +0.364) | 0.016 |
| Version 2 against the doc agent alone, on Cerebras | 100 | +0.000 (−0.050 to +0.060) | 1.00 |
| — domain-relevant | 34 | −0.088 (−0.206 to +0.029) | 0.38 |
| — metrics-generated | 33 | +0.091 (+0.000 to +0.212) | 0.25 |
| — novel-generated | 33 | +0.000 | 1.00 |
| Version 2 against its own drafts (the validator) | 100 | −0.020 (−0.050 to +0.000) | 0.50 |
| Drafts against the doc agent alone (routing and the specialists) | 100 | +0.020 (−0.030 to +0.070) | 0.69 |

On the 55 doc and hybrid answers, faithfulness rises from the doc agent's 0.49 to 0.82 (+0.327, from +0.200 to +0.455; p = 0.0001), and from the drafts' 0.53 (+0.291, from +0.164 to +0.418; p = 0.0002).

## Decision

**Adopt version 2 as the copilot** ([ADR-0026](../decisions/0026-copilot-v2.md)). It closes the gap to the doc agent alone (0.65 each) where version 1 trailed by 0.16, with more figure questions right, and answers the doc and hybrid questions far more faithfully (0.82 against 0.49). It doesn't beat the doc agent alone on correctness: what the data agent adds on figure questions, the validator and two drafts still give back on analyst questions.

What's left, for later steps:

- **Domain-relevant questions** are still 3 behind the doc agent alone. Two are revisions that drop what the reference wants, so a revision that loses a fact a judge would count is the next thing to look at.
- **The rules were written on these dev questions.** The routing set agrees with r2 on every question, but the FinanceBench test split, opened once when the copilot is final, is the only fair measure of the whole.

**Limits:** one run of each system on the 100 dev questions, so a few questions move each comparison; the changes were written from version 1's losses on the same questions; the judges are models, checked against reference labels from a stronger model, not a person ([ADR-0014](../decisions/0014-answer-judge.md)); version 1 can be reproduced from commit `789f825`.

## Logs

- Runs (question ids, verdicts and metrics only): [`eval/results/copilot/copilot-v2/dev/`](../../eval/results/copilot/copilot-v2/dev/) for the agent metrics; [`eval/results/correctness/`](../../eval/results/correctness/) and [`eval/results/faithfulness/`](../../eval/results/faithfulness/) for `copilot-v2` and `copilot-v2-drafts`, judged by `qwen-3.8-27b`; [`eval/results/latency/copilot-v2.json`](../../eval/results/latency/copilot-v2.json); router r2 on the routing set in [`eval/results/routing/llm-r2-gpt-oss-120b-cerebras/dev/`](../../eval/results/routing/llm-r2-gpt-oss-120b-cerebras/dev/).
- The answers, drafts and traces: `data/processed/answers/copilot-v2/`, `copilot-v2-drafts/` and `data/traces/copilot-v2.jsonl` (local: FinanceBench's licence keeps answers to its questions out of the repository).
- Reproduce ([runbook](../runbooks/running-evaluations.md#run-the-copilot-end-to-end)), with `FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b` and `FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b` set:

  ```bash
  uv run poe run-copilot --run copilot-v2
  uv run poe judge-answers --run copilot-v2
  uv run poe check-faithfulness --run copilot-v2
  uv run poe judge-answers --run copilot-v2-drafts
  uv run poe check-faithfulness --run copilot-v2-drafts
  uv run poe run-router --router llm --role strong --run llm-r2-gpt-oss-120b-cerebras
  uv run poe compare-runs eval/results/correctness/copilot-v1--qwen-3.8-27b-p2/dev eval/results/correctness/copilot-v2--qwen-3.8-27b-p2/dev --metric correct
  ```
