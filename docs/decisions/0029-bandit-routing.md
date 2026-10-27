# ADR-0029: Answer with one fixed model; keep the answer bandit behind a setting for Phase 9

- **Status:** Accepted
- **Date:** 2026-10-28
- **Phase:** 7

## Context

The doc agent writes every answer with gpt-oss-120b, and the answer call is most of a question's cost. Step 7.5 asks whether a bandit, learning from each answer's reward (1 if correct, less λ times its cost), would choose between answer models better than a fixed choice. On one provider (Cerebras, ADR-0024) the arms are gpt-oss-120b at its default and at low reasoning effort, and Qwen3.8 27B with reasoning off.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **A fixed arm: gpt-oss-120b at its default effort** | The most accurate arm (0.65); no exploration | Not the cheapest |
| A fixed arm: gpt-oss-120b at low effort | 15% cheaper; the best fixed arm when cost counts (λ ≥ 100) | 0.02 less accurate, not significant |
| ε-greedy over the three arms | Adapts to the price of a dollar without a rule | Below the best fixed arm at every λ on 100 questions (−0.02 to −0.11 a question) |
| UCB1 over the three arms | Explores where it is least sure | Also below the best fixed arm (−0.02 to −0.08) |

## Decision

The doc agent keeps answering with gpt-oss-120b at its default reasoning effort. `EpsilonGreedy`, its JSON state (`ArmChooser`) and the doc agent's hook stay behind `FRC_ANSWER_POLICY=epsilon-greedy`, default `fixed`; each answer names the arm that wrote it, so Phase 9 can reward the policy from readers' feedback.

## Evidence

[Bandit routing between answer models](../eval/bandit-routing.md), FinanceBench dev, 100 questions, each arm answering from the same sources:

- **Arms:** correct 0.65, 0.63 and 0.61 (no difference significant, Holm p = 0.86); $0.00195, $0.00166 and $0.00507 a question.
- **Replays over 2,000 orders:** at λ = 0, ε-greedy 0.630 and UCB1 0.629 against 0.650 for the best fixed arm and 0.710 for the oracle; at λ = 100, 0.425 and 0.408 against 0.464; at λ = 300, 0.022 and 0.053 against 0.133.

## Consequences

- No change to the copilot's answers or costs.
- If cost must fall, low reasoning effort is the measured first step: 15% cheaper, with a two-point lower accuracy this sample can't distinguish from none.
- On Cerebras, Qwen is the expensive model, not the cheap one: a cost fallback should never route to it there.
- A bandit could only pay off over many more rewards than 100, or with something about the question to go on: the arms trade places by question type (Qwen does better on novel questions, worse on domain ones), which a contextual policy could learn and a context-free one can't.

## References

- Sutton and Barto, *Reinforcement Learning: An Introduction*, 2nd ed., 2018, chapter 2.
- Auer, Cesa-Bianchi and Fischer, [Finite-time Analysis of the Multiarmed Bandit Problem](https://link.springer.com/article/10.1023/A:1013689704352), 2002.
- Li et al., [Unbiased Offline Evaluation of Contextual-bandit-based News Article Recommendation Algorithms](https://arxiv.org/abs/1003.5956), 2011.
- [ADR-0024](0024-second-provider.md); the [bandit routing guide](../concepts/bandit-routing.md).
