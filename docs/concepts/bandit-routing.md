# Bandit routing between answer models

> Learn, from the rewards answers earn, which model setting is worth its cost, while still answering every question.

**Lands in:** Phase 7 · **Code:** `src/copilot/answer/bandit.py`, `src/copilot/eval/bandit.py`, `scripts/run_answer_arm.py`, `scripts/replay_bandit.py`

## What it is

A **multi-armed bandit** is a repeated choice among options, the arms, each of which pays a reward drawn from a distribution the chooser doesn't know. Every choice both earns a reward and teaches something about the arm chosen, so a good policy balances **exploitation** (take the arm that has paid best so far) against **exploration** (try the others, which might be better). Regret is what a policy loses against always taking the best arm, had it been known.

Here an arm is a way to write the doc agent's answer: gpt-oss-120b at its default reasoning effort (the copilot's `strong` role today), the same model with less reasoning (`strong-low`), or Qwen3.8 27B with reasoning off (`fast`). An answer's **reward** is 1 when the judge counts it correct and 0 when not, minus λ times its cost in dollars: λ is the price of a dollar in right answers, so λ = 0 asks only for accuracy, and λ = 300 says that $0.0033 is worth a whole right answer.

**ε-greedy** takes the best arm so far except with probability ε, when it takes one at random; a decaying ε (here ε_t = 1 / (1 + t/10), after one try of every arm) explores early and exploits more as its averages firm up. **UCB1** (Auer et al., 2002) explores where it is least sure instead of at random: it takes the arm with the highest average plus a bonus, c·√(2 ln t / n), that shrinks as the arm is tried more often.

## Why we need it here

The answer call is most of a question's cost, and the strong model writes every answer. A cheaper setting might be right as often on some questions, and which setting is worth its price depends on the price of a dollar, which differs between a free demo and a paid deployment. A bandit can make that choice from rewards as they arrive, without a fixed rule, once the copilot collects rewards online (Phase 9). Before trusting one online, it should be shown offline, on answers already graded, to beat a fixed choice on the same questions.

## How it works

1. **The arms answer the same evidence** (`poe run-answer-arm`). Each arm answers every dev question from the sources the doc agent's final answer was written from in its Cerebras run: one call a question, no search, so the arms differ in nothing but the model that writes. The `strong` arm's calls replay from the cache and reproduce that run's answers.
2. **The same judge grades them** (`poe judge-answers`), and each answer's cost comes from its tokens at the gateway's list prices.
3. **The reward table** has one row a question and one column an arm, for each λ.
4. **The replay** (`poe replay-bandit`, `copilot.eval.bandit`) shows a policy the questions in a random order and reveals only the reward of the arm it chose, as a live bandit would see it; over 2,000 orders, its average reward a question sits beside each fixed arm's and the oracle's (the best arm for each question, known in hindsight), the bounds on what any policy can do here.
5. **Online** (`FRC_ANSWER_POLICY=epsilon-greedy`), an `ArmChooser` picks each answer's arm and keeps its counts and averages in `data/processed/bandit/answer-arms.json`; the answer records its arm, so Phase 9's feedback can reward it through `ArmChooser.update`.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.answer.bandit` | The arms, the reward, `EpsilonGreedy` (with its state as JSON) and `ArmChooser` |
| `copilot.answer.generate.generate(role=, **params)` | Writes an answer with an arm's model setting |
| `copilot.answer.agent.DocAgent(arms=)` | Asks the chooser for each answer's arm, and names it in the answer |
| `scripts/run_answer_arm.py` | One arm's answers to the dev questions, from a run's stored sources |
| `copilot.eval.bandit` | Fixed, ε-greedy and UCB1 policies, the replay and its bounds |
| `scripts/replay_bandit.py` | The reward tables by λ, and every policy's replay |

## How we measured it

On FinanceBench dev ([report](../eval/bandit-routing.md)), the three arms answered the same sources: correct 0.65, 0.63 and 0.61 (no difference significant), at $0.00195, $0.00166 and $0.00507 a question. Replayed over 2,000 orders:

| Policy | λ = 0 | λ = 100 | λ = 300 |
|---|---|---|---|
| Best fixed arm | 0.650 (`strong`) | 0.464 (`strong-low`) | 0.133 (`strong-low`) |
| ε-greedy | 0.630 | 0.425 | 0.022 |
| UCB1 | 0.629 | 0.408 | 0.053 |
| Oracle | 0.710 | 0.530 | 0.170 |

Both learners earn less than the best fixed arm at every λ, so the copilot keeps a fixed arm, and the bandit waits behind `FRC_ANSWER_POLICY` for Phase 9's rewards ([ADR-0029](../decisions/0029-bandit-routing.md)).

## Pitfalls we hit

- **Too few rounds for arms this close.** A two-to-four-point difference in accuracy needs far more than 100 rewards to show; until it does, every exploring choice of a worse arm is a cost, so on 100 questions the best a learner can do is lose slowly to the best fixed arm.
- **The cheap model isn't always cheap.** On Cerebras's list prices, Qwen costs two and a half times as much a question as gpt-oss-120b; the roles' names (`fast`, `small`) describe the free tier, not every provider.
- **A fair comparison needs the same evidence.** Letting each arm run the whole doc agent would also change what it retrieves on a retry; answering from the stored sources isolates the answer model, at the price of leaving retries out.
- **The judge shares a model with an arm.** The evaluation's judge is Qwen, which is also the `fast` arm, so that arm's answers could be favoured; it still came last.

## Review questions

1. Why does a bandit that knows nothing at first lose to the best fixed arm on 100 questions, even if it ends up choosing that arm?
2. What does λ express, and how would you set it for a free demo and for a paid deployment?
3. Why must every arm answer from the same sources for the comparison to be fair, and what does that leave out of the doc agent's real cost?
4. When would a contextual bandit, one that sees something about the question before it chooses, do better than these?

## References

- Sutton and Barto, [Reinforcement Learning: An Introduction](http://incompleteideas.net/book/the-book-2nd.html), 2nd ed., 2018, chapter 2.
- Auer, Cesa-Bianchi and Fischer, [Finite-time Analysis of the Multiarmed Bandit Problem](https://link.springer.com/article/10.1023/A:1013689704352), 2002 (UCB1, decaying ε).
- Li, Chu, Langford and Wang, [Unbiased Offline Evaluation of Contextual-bandit-based News Article Recommendation Algorithms](https://arxiv.org/abs/1003.5956), 2011 (replaying logged rewards).
