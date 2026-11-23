# The answer bandit online: a week against its fixed arm

Phase 9, step 9.3 ([ADR-0036](../decisions/0036-bandit-online.md), [guide](../concepts/bandit-routing.md), [runbook](../runbooks/bandit-and-canary.md)). The bandit chose the doc agent's answer model on the live API from 15 November, with a daily canary of the project's own questions feeding it rewards. This report compares it with its randomized fixed arm over the canary's days from 15 to 22 November, as fixed before the data.

## Question

Does the bandit's policy earn at least the reward of the fixed answer model it would replace? ADR-0036's rule, set before any reward came in, keeps the bandit on only if it does.

## Setup

- **The arms,** ADR-0029's three settings of the answer call, on Cerebras:
  - `strong`: gpt-oss-120b at its default reasoning effort, the fixed arm;
  - `strong-low`: the same model at low effort;
  - `fast`: Qwen3.8 27B with reasoning off.
- **Two randomized groups.** A coin flip sent each paid answer to the fixed arm (the control) or to the policy, ε-greedy with ε = 0.2 / (1 + t/50) after t rewards. Both groups' rewards updated the arms' averages.
- **The reward,** quality alone (λ = 0): the faithfulness judge (prompt 1, Cerebras's Qwen with reasoning off) gave 1 when every cited sentence was supported by its source, and 0 otherwise.
- **The questions:** the canary asked the routing set's 30 dev questions on the doc route in turn, ten a day, and twenty on the weekdays of 16 to 20 November, each in a new conversation so that no answer came from the cache. The judge scored every canary answer.
- **The window** (`poe bandit-report --since 2026-11-15 --until 2026-11-23 --name one-week`): every answer an arm wrote from 15 November to the end of 22 November (UTC). Two weeks were planned. After the first day, before any comparison, the owner shortened them to one ([amendment](../decisions/0036-bandit-online.md#amendment-15-november-a-week-instead-of-two)).
- **The test:** each group's mean reward with a bootstrap interval, and the policy's difference from the control with a two-sample permutation test.

## Results

The window holds 119 judged answers. 118 come from the canary's eight days; the other is the answer to the one-question trial on 15 November, which went to the policy and was judged faithful.

| Day (UTC) | Asked | Back and judged | Note |
|---|---|---|---|
| 15 November | 10 | 9 | One failed: Groq refused the answer check's reply as invalid JSON (#122, fixed by #123) |
| 16 November | 20 | 9 | Asked on 15 November's quota by a slot GitHub started six and a half hours late; eleven got HTTP 429 (#126, fixed by #127) |
| 17 to 20 November | 20 a day | 80 | |
| 21 and 22 November | 10 a day | 20 | |

The API answered no visitor's question in the week: its request log holds only the canary's. So there are no visitors' judged answers or thumbs to compare, and no second answers.

| Group | Answers | Arms | Mean reward | 95% interval |
|---|---|---|---|---|
| Policy | 57 | `fast` 52, `strong-low` 3, `strong` 2 | 0.930 | 0.860 to 0.982 |
| Control | 62 | `strong` 62 | 0.855 | 0.758 to 0.935 |

- **By arm,** both groups together: `fast` 50 of 52 judged faithful (0.96), `strong` 54 of 64 (0.84), `strong-low` 2 of 3.
- **The policy settled on `fast` quickly.** It tried all three arms on 15 November. From 18 November every policy answer used `fast`, and on 17 November nine of ten did.
- **Refusals.** The policy's answers included 4 refusals (3 from `fast`, 1 from `strong-low`), and the control's 1. A refusal that cites what the filing does say can be judged faithful: two of `fast`'s three were. So the reward reads "nothing unsupported", and a refusal without citations scores 0.
- **The zeros.** All 9 of the control's zeros came from `strong`: 8 answers with a sentence the judge found unsupported, and 1 refusal. The policy's 4 zeros: 1 answer each from `fast` and `strong`, and 2 refusals.
- **Cost.** The log keeps each answer's whole cost at list prices: $0.0084 on average for the policy's answers and $0.0056 for the control's. On Cerebras, Qwen costs more per token than gpt-oss-120b, so the policy's answers cost about half as much again. The judge's call came to $0.0023 an answer in the policy's group and $0.0025 in the control's.
- **Spend.** The bandit's paid calls (its arms and its judge) cost at most $0.129 in a day (17 November), against the $0.25 cap, and $0.699 in all from the trial on 14 November to 22 November. Days of twenty cost $0.108 to $0.129, and days of ten $0.053 and $0.065. The cap was never reached.

## Comparison

| Reward | Policy | Control | Difference | 95% interval | p |
|---|---|---|---|---|---|
| The judge (λ = 0), the rule's measure | 0.930 | 0.855 | +0.075 | −0.039 to +0.188 | 0.25 |
| The judge less 10 × cost | 0.846 | 0.799 | +0.047 | −0.066 to +0.157 | 0.42 |
| The judge less 100 × cost | 0.088 | 0.298 | −0.210 | −0.386 to −0.036 | 0.02 |

- **On the rule's measure, the two can't be told apart.** The policy's mean is the higher, but the interval of the difference spans zero.
- **Cost changes the order.** ADR-0036 keeps each answer's cost so that the reward can also be read with a cost penalty, as ADR-0029's replay did (the reward less λ times the answer's cost in dollars). At ADR-0029's λ = 100, where each cent an answer costs takes 1 off its reward, the control wins, and significantly. The two break even at λ of about 26.

## Decision

**The bandit stays on.** By the rule, the policy's mean reward on the canary's judged answers (0.930) is at least the control's (0.855). The difference isn't significant, so the rule decides, as ADR-0036 expected it would. Nothing else changes:

- the coin flip, the arms, the policy, the rewards and the $0.25 cap stay as they are;
- the canary goes back to ten questions a day;
- the control group stays, so a later window can be compared the same way.

## Limits

- **The judge shares a model with the arm the policy chose.** The judge is Qwen, and so is `fast`, which wrote 52 of the policy's 57 answers. A judge may favour its own model's writing, so part of `fast`'s lead could be the judge's taste. A judge from another model family would separate the two. Offline, on correctness rather than faithfulness, `fast` came last of the three arms (0.61, against 0.65 for `strong`; not significant; [report](bandit-routing.md)).
- **Faithfulness isn't correctness.** The reward says every cited sentence holds up against its source. It doesn't say that the answer is right or complete, and a refusal that cites can earn it.
- **The reward ignores price, by the owner's choice.** The policy's answers cost about half as much again as the control's. With a cost penalty of 100 the control wins. The cap bounds the money: the bandit spent under $0.13 on its busiest day.
- **The project's own questions.** The canary asks 30 questions in turn, and the week's plan asked 20 of them five times and 10 three times (16 November lost eleven). Both groups drew from the same days and questions, so the comparison is fair, but visitors' questions may differ.
- **A small sample.** About 60 judged answers a group can show only a difference of roughly 12 to 17 points.
- **An adaptive policy.** The policy's early answers explored, and its later ones exploited, so its group's mean mixes both. That is the cost of learning, and it is part of what the rule compares.

## Logs

- **The comparison:** [`eval/results/bandit-online/one-week/summary.json`](../../eval/results/bandit-online/one-week/summary.json): counts, means, intervals, p-values and the decision.
- **The log:** Firestore `bandit-answers`, one record per answer an arm wrote: the arm, the group, canary or visitor, the cost and the rewards, with no question or answer text. `poe bandit-report` keeps a copy under `data/processed/bandit/`, which isn't committed.
- **The canary's days:** `canary/history.jsonl` and `canary/runs/` on the `eval-history` branch.
- **The spend by day:** the API's `llm.spend` events (labels `bandit.arm` and `bandit.judge`); the days' `quotas` documents in Firestore expire.
