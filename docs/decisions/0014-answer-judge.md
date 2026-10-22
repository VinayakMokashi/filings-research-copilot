# ADR-0014: Grade answers with a rubric-bound model judge, checked against reference labels

- **Status:** Accepted
- **Date:** 2026-10-23
- **Phase:** 3

## Context

From Phase 3 on, every change to the agent needs a correctness number on the 100 dev questions, and FinanceBench's reference answers can't be matched by rule: a bare figure in the question's units ("$1577.00" for USD millions), a yes or no with its reasons, or a few sentences. Grading every run by hand doesn't scale. A model can grade, but a model judge has its own errors (leniency, inconsistency, a liking for text like its own, poor arithmetic), so its numbers mean something only once they have been checked against labels it didn't produce.

## Options considered

| Question | Options |
|---|---|
| Who grades | String or number matching; a person for every run; a model judge checked against reference labels on a sample |
| What the judge reads | The reference and the answer; also the question and FinanceBench's note on how the reference was reached; also code-computed comparisons of their figures |
| Which model | The answer model itself (gpt-oss-120b); a smaller model of the same family (gpt-oss-20b); a different family (Qwen) |
| Outcomes | A score from 1 to 5; correct or incorrect; correct, incorrect or refused |
| Reference labels | A person, by hand; a stronger model given the same page; none, with judge-to-judge agreement only |

## Decision

1. **A model judge with a written rubric** (`copilot.eval.judge`), at temperature 0 in JSON mode, returning correct or incorrect with a one-sentence reason. Refusals are a third outcome that needs no judge, as in the FinanceBench paper.
2. **The rubric**: numbers match at the reference's precision or within 1%; units and notation may differ; a judgement must reach the same conclusion, and any figure the answer gives for something the reference quantifies must match too; every part of a multi-part question must match; extra detail is fine unless it contradicts the reference.
3. **Arithmetic in code**: `closest_figures` pairs each reference figure with the answer's closest figure, allowing for thousands, millions and billions and for percentages written as fractions, and the judge gets the distances. The judge decides whether two figures measure the same thing.
4. **The default judge is Qwen** (the fast role), a different family from the answer model; gpt-oss-20b is the second judge.
5. **Checked against reference labels from a stronger model.** 44 dev questions were drawn by question type with a fixed seed before any answer was judged, and answered first. The 41 answered ones were labelled on a private page that shows exactly what the judge sees, plus the rubric, and never the judge's verdict. The labels came from a Claude model, not a person; the plan's hand-labelling step was replaced, and a person check is still to do.

## Evidence

41 labelled answers of run `doc-agent-v3-full` (29 correct, 12 incorrect by the labels; [data card](../data/answer-labels.md)):

| Judge (rubric v2) | Agreement with the labels | Cohen's kappa (95% interval) | Says correct |
|---|---|---|---|
| **Qwen 3.8 27B** | **41 of 41** | **1.00** | 0.71 |
| gpt-oss-20b | 38 of 41 (0.93) | 0.84 (0.63 to 1.00) | 0.63 |
| The labels themselves | | | 0.71 |

- gpt-oss-20b is the stricter judge: all three of its disagreements are answers the labels call correct.
- On all 94 answered dev questions, the two judges agree on 87 (0.93), kappa 0.83 (0.69 to 0.93), and say correct for 65 and 64.
- The first rubric left the 1% rule to the model and was silent on figures under a judgement. Changing both moved 3 verdicts on 22 answers, each in the intended direction: an answer 0.44% from the reference became correct, and two whose figures were off became incorrect.
- Each verdict costs about 660 tokens on the fast model. Both judges returned a valid verdict for every one of the 94 answered dev questions.

## Consequences

- The judge is checked against a stronger model, not a person, so its numbers carry that caveat wherever they are reported. Models share failure modes, so perfect agreement between two of them says less than agreement with an analyst would; 20 answers labelled by hand would settle it.
- Judging a 100-question run costs about 66,000 tokens on the fast model, leaving the strong model's daily quota to the agent.
- Verdicts are named by judge model and prompt version, so a rubric change starts a new set of verdicts instead of mixing two.
- The labels belong to one answers run. A later agent can be judged by the checked judge; a new rubric or judge needs labels again, and the sample's ids are committed so the same questions can be labelled again.

## References

- Zheng et al., [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685), 2023.
- Islam et al., [FinanceBench](https://arxiv.org/abs/2311.11944), 2023.
- Cohen, A Coefficient of Agreement for Nominal Scales, 1960.
- Guide: [LLM as judge](../concepts/llm-as-judge.md).
