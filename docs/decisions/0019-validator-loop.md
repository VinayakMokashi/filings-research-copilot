# ADR-0019: Check every cited sentence before an answer is shown, and revise what fails at most twice

- **Status:** Accepted
- **Date:** 2026-10-25
- **Phase:** 5

## Context

The copilot's answers promise that each sentence is supported by the source it cites. The doc agent kept that promise in 63% of its answers to FinanceBench dev questions: 35 of its 94 answers had at least one sentence its citations didn't support, mostly judgements that went beyond their pages and figures worked out without the calculator ([report](../eval/doc-agent-dev.md)). A reader can't tell those sentences from the supported ones.

The plan's step 5.3 asks for a claim-level check inside the graph, a retry with feedback at most twice, then an abstention. Three constraints shape it:

- **Independence.** The evaluation's faithfulness judge is Qwen3.8 27B; a loop that rewrote answers until that model approved would raise the measured faithfulness by construction.
- **Cost.** Every doc and hybrid answer passes through the check, so it is paid on most questions.
- **The free tier.** Each model has its own daily token cap.

## Options considered

| Option | For | Against |
|---|---|---|
| No check (Phase 3) | No cost or latency | A third of the answers carry a sentence their citations don't support |
| Check and flag: show the unverified sentences, change nothing | One cheap call; the answer stays whole | Leaves the unsupported sentences in front of the reader, who must judge them |
| **Check, revise at most twice, then keep only the verified sentences or decline** | Faithful answers rise from 0.64 to 0.85 on dev; no answer became unfaithful | About $0.0008 an answer; it removes judgements the sources don't state, which domain-relevant questions reward |
| The same loop with the evaluation's judge as the checker | Closest to the grader | Tunes the copilot to its grader, so its faithfulness can no longer be measured; about ten times the checker's price per token |

## Decision

1. **The `validate` node checks doc and hybrid answers** that answer the question; data answers (which cite their query as a whole), refusals, small talk and declines pass straight on.
2. **The checker is the `small` role,** gpt-oss-20b, with the faithfulness check of Phase 3: each sentence against the sources it cites. It differs from the writer (gpt-oss-120b) and from the evaluation's judges (Qwen3.8 27B).
3. **A failing answer goes back to its writer,** on the `strong` role with its own rules and sources and the failing sentences listed, at most twice.
4. **After two failed revisions** the answer keeps its verified sentences; with none left, it becomes a refusal that says what couldn't be verified.
5. **The response reports the check:** whether it ran, whether the final answer passed, the number of revisions and any sentences cut.

## Evidence

On the doc agent's 100 stored dev answers, run through the loop and graded by the Phase 3 judges ([report](../eval/validator-dev.md)):

- **Faithfulness:** 0.628 to 0.848; on the 92 answered both times, +0.207 (+0.130 to +0.293), p = 0.0001. Nineteen answers went from unfaithful to faithful, none the other way.
- **Correctness:** 0.65 to 0.61, -0.040 (-0.100 to +0.010), p = 0.28. Figure questions kept theirs (0.879); domain-relevant questions fell from 0.588 to 0.441, p = 0.063, every loss among the revised answers.
- **The checker against the judge:** of the 35 answers the judge found unfaithful, the checker revised 25; of the 59 it found faithful, 3.
- **Cost:** $0.0008 an answer at list prices, about 70% on top of the doc agent's $0.0011; the 28 revised answers carry most of it.

## Consequences

- **Every checked answer pays one more call,** on the small model's own quota, and each revision one more call to the strong model and another check.
- **Judgement questions lose their judgement** when it rests on general knowledge, a usual benchmark or an industry norm, rather than on the sources. The copilot's rules already forbid outside knowledge; the loop enforces them. Letting an answer give an assessment labelled as its own, apart from the cited facts, is an open question for a later phase.
- **Checked is not certain:** the checker passed 10 of the 35 answers the judge found unfaithful.
- **The graph's loop is an edge,** `validate` to `revise` and back ([ADR-0018](0018-graph-design.md)); the end-to-end evaluation (step 5.6) measures the copilot with it in place.

## References

- Madaan et al., [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651), 2023.
- Gao et al., [RARR: Researching and Revising What Language Models Say, Using Language Models](https://arxiv.org/abs/2210.08726), 2023.
- The [validator loop guide](../concepts/validator-loop.md) and the [dev report](../eval/validator-dev.md).
