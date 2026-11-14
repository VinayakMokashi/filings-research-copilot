# ADR-0036: Run the answer bandit online within $0.25 a day, against a randomized fixed arm, with a daily canary

- **Status:** Accepted
- **Date:** 2026-11-15
- **Phase:** 9

## Context

Step 7.5 replayed ε-greedy and UCB1 over 100 judged dev answers. Both earned less than the best fixed arm, so the copilot kept one fixed answer model, with the bandit behind a setting until rewards came from real use ([ADR-0029](0029-bandit-routing.md)). Phase 9 brings it online.

The owner set the terms on 10 November:

- the bandit gets its own cap of $0.25 a day, and at the cap answers go back to the fixed path on Groq;
- ε decays from 0.2;
- rewards come from visitors' thumbs and a judge on a sample of its answers, inside the same cap;
- after two weeks, it is compared with the fixed arm, with intervals, and switched off if it earns less.

One fact changed the plan. From 3 to 15 November the live API answered 3 questions and received no rating. At that rate two weeks would bring no rewards, and a comparison would have nothing to compare. So on 15 November the owner also approved a daily **canary**: a scheduled job that asks the live copilot some of the project's own questions, with the judge scoring every answer, inside the bandit's cap.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Compare the bandit's rewards with its own `strong` arm's | No split | The policy's average contains that arm's rewards, and its choices depend on them: two overlapping, adaptive samples, with no fair interval |
| Compare with answers from the fixed Groq path | Free | Another provider, other times and other questions: not a like-for-like comparison (ADR-0024) |
| **A coin flip for each paid answer: the fixed arm or the policy, both on Cerebras** | Two randomized groups on the same traffic and provider, so an interval means what it says | Half the paid answers don't follow the policy |
| Visitors' traffic only | Real questions | About one question every four days so far |
| **A daily canary of the project's own questions, judged** | Rewards every day; the only daily check of the deployed service end to end | Questions the project wrote, scored by a model, not visitors' verdicts |

## Decision

1. **What the bandit chooses:** the model setting of the doc agent's answer calls, among ADR-0029's three arms on Cerebras:
   - `strong`, gpt-oss-120b at its default reasoning effort, the fixed arm;
   - `strong-low`, the same model at low effort;
   - `fast`, Qwen3.8 27B with reasoning off.

   That covers the doc route, the data agent's handoffs to the doc agent, and the hybrid's one-company path. The rest of a run (the router, the rewrites, the validator) stays on Groq.
2. **Two randomized groups.** For each answer the bandit pays for, a coin flip sends it either to the fixed arm (the control) or to the policy, with probability 1/2 each. Both groups' rewards update the arms' averages: a reward says how good an arm is, whoever chose it.
3. **The policy:** ε-greedy, with ε = 0.2 / (1 + t / 50), where t is the number of rewards so far. Each arm is tried once first.
   - **The reward is quality alone (λ = 0),** because the cap already bounds the money.
   - **Each answer's cost is kept,** so the report can show a reward with a cost penalty too, as ADR-0029 did.
4. **The rewards,** each between 0 and 1:
   - **a thumbs up** is 1, and a thumbs down 0;
   - **the judge** gives 1 when every cited sentence is supported, and 0 otherwise, including a refusal. It is the nightly evaluation's faithfulness check (prompt 1), on Cerebras's Qwen with reasoning off. It scores half of the visitors' bandit answers, chosen at random, and every canary answer.
   - **No reward** comes from a retry's answer, which follows a thumbs down and so a harder question than the arm usually gets, or from an answer served from the cache.
5. **State,** in Firestore `bandit/answer-arms`: each arm's count and reward sum, raised with atomic increments, so no transaction is needed.
6. **The cap.** `FRC_BANDIT_DAILY_USD` is 0.25 in the deployment and 0 (off) everywhere else.
   - **What counts:** the arms' calls and the judge's, in `quotas/<day>.bandit_usd`.
   - **When it is checked:** before each answer's choice. At the cap, or when the day's spend can't be read, the answer takes the fixed path on Groq.
   - **Calls in flight** can pass the cap by a fraction of a cent, as with ADR-0033's fallback.
   - **If an arm's call fails,** the answer is written once more on the fixed path and earns no reward.
7. **The log:** `bandit-answers/<request id>`: the arm, the group, canary or visitor, the route, the cost, and the rewards as they come. The report reads it.
8. **The canary.**
   - **When:** a GitHub Actions workflow, once a day.
   - **What:** it asks 10 of the routing set's 30 dev questions on the doc route (the project's own; the test split stays closed), a different ten each day in turn, each in a new conversation, so the answer cache is bypassed.
   - **As whom:** its own account, `github-canary`, which may call the API and nothing else, reached keylessly through workload identity federation as the deploys are.
   - **What it keeps:** metrics only, in `canary/history.jsonl` on the `eval-history` branch. A failed request fails the run and opens an issue.
   - **When it runs:** only while the bandit is on.
9. **The comparison, fixed before the data.**
   - **When:** after 14 days with the bandit on.
   - **How:** the report compares the policy group's mean reward with the control group's, with bootstrap intervals and a permutation test. Canary rewards (the judge's) and visitor rewards (thumbs) are kept apart.
   - **The rule (the owner's):** the bandit stays on only if the policy's mean reward on the canary's judged answers, the larger sample, is at least the control's. Otherwise the cap is set to 0. When the interval spans zero, the report says the two can't be told apart.

## Consequences

- **Money.** The bandit can spend at most $0.25 a day, about $7.50 a month; the canary alone is expected at $0.05 to $0.08 a day. With the nightly evaluation (at most about $15 a month) and the paid fallback (at most $0.50 a day), every Cerebras spend is capped. The trial credit's end on 22 December doesn't change this bill, which Cerebras sends.
- **A judged visitor answer waits for the judge,** a few seconds, before its stream ends.
- **The canary counts against the day's total quota** of 200 questions, ten a day.
- **The comparison's power is low.** With about 70 judged answers in each group after two weeks, only a difference of roughly 12 to 16 points would show, depending on the share judged faithful. Most likely the report will say the policy and the fixed arm can't be told apart, and the owner's rule then decides.
- **A judge shares a model with an arm.** The judge is Qwen, which is also the `fast` arm, as in ADR-0029; the report says so.

## References

- Sutton and Barto, *Reinforcement Learning: An Introduction*, 2nd ed., 2018, chapter 2.
- Kohavi, Tang and Xu, *Trustworthy Online Controlled Experiments*, Cambridge University Press, 2020 (randomized comparisons online).
- Li et al., [A Contextual-Bandit Approach to Personalized News Article Recommendation](https://arxiv.org/abs/1003.0146), WWW 2010.
- [ADR-0029](0029-bandit-routing.md) (the arms and the replay), [ADR-0033](0033-capped-paid-fallback.md) (a daily cap in Firestore), [ADR-0034](0034-nightly-evaluation.md) (the judge, `eval-history`), [ADR-0035](0035-preference-pairs.md) (retries).
