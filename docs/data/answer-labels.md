# Data card: reference labels for the answer judge

| | |
|---|---|
| **What it is** | Correctness labels for 41 of the doc agent's dev answers, used to check the [LLM judge](../concepts/llm-as-judge.md) |
| **Files** | [`eval/labels/answer-correctness-sample.json`](../../eval/labels/answer-correctness-sample.json) (the 44 sampled question ids, seed 0) and [`eval/labels/answer-correctness.jsonl`](../../eval/labels/answer-correctness.jsonl) (one line per label: id, answers run, labeller, label) |
| **Labeller** | A Claude model, given the same labelling page a person would use. **Not a person**: see known issues |
| **Licence** | MIT for the labels. The questions, reference answers and model answers they refer to stay out of the repository (FinanceBench is CC BY-NC 4.0) |
| **Built** | 2026-10-22, on the answers of run `doc-agent-v3-full` |
| **Used for** | `poe judge-agreement`: agreement and Cohen's kappa between each judge and these labels ([ADR-0014](../decisions/0014-answer-judge.md)) |

## What's in it

| Question type | Labelled | Correct | Incorrect |
|---|---|---|---|
| Domain-relevant | 13 | 10 | 3 |
| Metrics-generated | 14 | 13 | 1 |
| Novel-generated | 14 | 6 | 8 |
| **All** | **41** | **29** | **12** |

No answer was labelled unsure, and none has a note.

## How it was built

1. **The sample.** `poe label-sample` drew 44 of the 100 dev questions, stratified by question type (15 domain-relevant, 15 metrics-generated, 14 novel-generated) with seed 0, before any answer was judged. The agent then answered those questions first (`poe answer-questions --first`).
2. **What the labeller saw.** For each of the 41 answered questions (the agent refused the other three, and a refusal needs no label), a private labelling page showed what the judge sees: the question, the reference answer, FinanceBench's note on how it was reached, the agent's answer without citation markers, and the computed comparisons of their figures. The page also showed the judge's rubric. It never showed the judge's verdicts.
3. **The labels.** Each answer was marked correct, incorrect or unsure on the page; `poe judge-agreement` reads the decided ones.

## Known issues

- **A model, not a person.** The plan called for labels by hand. These came from a Claude model, so they measure how often the judge agrees with a stronger model, not with a person. Models share failure modes (leniency on fluent answers, the same misreadings of a rubric), so agreement between them overstates how often the judge would agree with an analyst. A person check of the judge is still to do.
- **One labeller.** There is no second labeller to measure the labels' own consistency.
- **One run.** The labels belong to `doc-agent-v3-full`. A later agent's answers differ, so they can be judged by the checked judge but not compared with these labels directly; the sample's ids are committed, so the same questions can be labelled again.
- **Small.** With 41 labels, a 95% interval on agreement near 0.9 spans about ±0.1, and on kappa about ±0.2.
