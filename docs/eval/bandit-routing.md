# Bandit routing between answer models

Phase 7, step 7.5. FinanceBench dev, 100 questions; offline replays of the judged answers, no new questions.

## Question

The strong model writes every answer the doc agent gives, and the answer call is most of a question's cost. Would a bandit that learns from each answer's reward (right or wrong, less a price for its cost) choose between answer models better than always using one?

## Setup

- **The arms** (`copilot.answer.bandit.ARMS`), the settings this project can run on one provider (Cerebras, ADR-0024), which serves two of its models: gpt-oss-120b at its default reasoning effort (`strong`, the copilot's answer model), the same model at low effort (`strong-low`), and Qwen3.8 27B with reasoning off (`fast`). gpt-oss-20b, the `small` role, is served only on Groq's free tier, whose daily quota couldn't answer 100 questions in reasonable time, so it isn't an arm.
- **The same evidence** (`poe run-answer-arm`): each arm answered every dev question from the sources the doc agent's final answer was written from in its Cerebras run (`doc-agent-v4-cerebras`), one call a question with no search, so the arms differ only in the model that writes. The `strong` arm replayed all 100 calls from the cache, and its judgements match that run's on 100 of 100 questions.
- **The judge:** the same as every Cerebras run (Qwen3.8 27B, reasoning off, prompt p2; ADR-0014). It also is the `fast` arm's model, which could favour that arm's answers.
- **Costs** from each answer's tokens at LiteLLM's list prices for Cerebras.
- **Rewards:** 1 for a correct answer, 0 otherwise, less λ times its cost in dollars, for λ = 0 (accuracy alone), 100 and 300 (a right answer is worth $0.01 or $0.0033).
- **Policies,** replayed over 2,000 random orders of the questions, each seeing only the reward of the arm it chose (`poe replay-bandit`): ε-greedy with ε = 1 / (1 + t/10) after one try of each arm, UCB1 (c = 1), every fixed arm, and the oracle (each question's best arm in hindsight).

## Results

### The arms

| Arm | Model | Correct | Against `strong` (Holm-adjusted) | Cost a question |
|---|---|---|---|---|
| `strong` | gpt-oss-120b, default effort | 0.65 | | $0.00195 |
| `strong-low` | gpt-oss-120b, low effort | 0.63 | −0.020 (−0.070 to +0.030), p = 0.86 | $0.00166 |
| `fast` | Qwen3.8 27B, reasoning off | 0.61 | −0.040 (−0.110 to +0.030), p = 0.86 | $0.00507 |

No arm is significantly more or less accurate than the others. On Cerebras, Qwen costs two and a half times as much a question as gpt-oss-120b, so the `fast` role is the dear one there. By question type, the arms trade places: Qwen gets 19 of 33 novel-generated questions right against 17, and 13 of 34 domain-relevant ones against 19. 55 questions are right with every arm and 29 with none; only 8 are right with one arm alone.

### The replays

| Policy | λ = 0 | λ = 100 | λ = 300 |
|---|---|---|---|
| Fixed: `strong` | **0.650** | 0.455 | 0.066 |
| Fixed: `strong-low` | 0.630 | **0.464** | **0.133** |
| Fixed: `fast` | 0.610 | 0.103 | −0.910 |
| ε-greedy (spread over orders) | 0.630 (0.59 to 0.66) | 0.425 (0.39 to 0.46) | 0.022 (−0.05 to 0.09) |
| UCB1 | 0.629 (0.59 to 0.67) | 0.408 (0.36 to 0.45) | 0.053 (0.01 to 0.09) |
| Oracle | 0.710 | 0.530 | 0.170 |

Average reward a question. **At every λ, both learners earn less than the best fixed arm**: by 0.02 at λ = 0, and by 0.04 to 0.11 when cost counts. Over 100 questions they keep sampling every arm (at λ = 0, ε-greedy took the best arm on only 39% of questions, and Qwen on 27%), because the arms' accuracies are too close, two to four points, for 100 rewards to tell them apart before the questions run out. The oracle's lead (0.71 against 0.65) shows the arms do differ question by question, but a policy that sees nothing about a question can't use that.

## Decision

**Keep the fixed `strong` arm; don't route answers with a bandit** ([ADR-0029](../decisions/0029-bandit-routing.md)). The policy, its JSON state and the doc agent's hook stay behind `FRC_ANSWER_POLICY=epsilon-greedy` (default `fixed`), and each answer names its arm, so Phase 9 can feed it rewards from readers' feedback over far more questions than 100. Two findings stand on their own:

- **Low reasoning effort** costs 15% less at a two-point lower accuracy that isn't significant: the setting to try first if cost has to fall.
- **Qwen isn't the cheap model on Cerebras.** At its list price it costs 2.6 times as much a question, so it shouldn't be the fallback for cost.

**Limits:** 100 questions; one judge, which shares the `fast` arm's model; the arms answered the strong model's retrieved sources, so the comparison leaves out what a different model would have retried; gpt-oss-20b isn't an arm.

## Logs

- Answers: `data/processed/answers/arm-{strong,strong-low,fast}/dev/` (git-ignored); judgements in [`eval/results/correctness/arm-*--qwen-3.8-27b-p2/`](../../eval/results/correctness/), compared in [`_comparisons/answer-arms`](../../eval/results/correctness/_comparisons/answer-arms.md).
- Replays: [`eval/results/bandit/answer-arms/dev/`](../../eval/results/bandit/answer-arms/dev/summary.md).
- Reproduce:

  ```bash
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \
  FRC_LLM_TOKENS_PER_MINUTE=100000 uv run poe run-answer-arm --arm strong-low --run arm-strong-low
  uv run poe judge-answers --run arm-strong-low
  uv run poe replay-bandit --arms strong=arm-strong,strong-low=arm-strong-low,fast=arm-fast \
      --lambdas 0,100,300 --name answer-arms
  ```
