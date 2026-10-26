# Self-consistency on figure answers: dev evaluation

Phase 5, step 5.4. FinanceBench dev, the 33 figure (metrics-generated) questions; the held-out test split was not opened.

## Question

A model answering at temperature 0 repeats its mistakes: ask again and the same wrong figure comes back. Does sampling more answers to a figure question and keeping the figure most of them give make the doc agent's figure answers correct more often, and is the gain worth the extra answer calls?

## Setup

- **Answers:** the doc agent's stored answers to the 33 dev figure questions (`doc-agent-v4-full`, Phase 3): 31 answers and 2 refusals. `poe self-consistency` adds the votes to each, so the comparison is paired: the same questions, the same sources and the same first answers ([guide](../concepts/self-consistency.md)).
- **Votes (k = 3):** the stored answer, written at temperature 0, is the first vote. Two more answer calls over the same numbered sources, with the doc agent's own model (gpt-oss-120b) and prompt, sample at temperature 0.7, each with its own seed.
- **The vote:** each answer's main figure is the first one it gives, read by the judge's figure parser. Answers within 1% of each other form a group, refusals form one too, and the largest group wins; a tie keeps the first, deterministic answer.
- **Graded** by the correctness judge of Phase 3, Qwen3.8 27B with rubric prompt 2 and figures compared by code ([ADR-0014](../decisions/0014-answer-judge.md)), served by Groq as for the source run.
- **Tests:** a paired permutation test ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

| | Doc agent (Phase 3) | Self-consistency, k = 3 |
|---|---|---|
| Correct | 0.879 (0.76 to 0.97) | 0.879 (0.76 to 0.97) |
| Incorrect | 0.061 | 0.061 |
| Refused | 0.061 | 0.061 |

**No verdict changed.** Both runs answered the same 29 questions correctly, and the same two incorrectly; the same two were refused.

**How the votes fell:**

- **All three votes agreed on 24 questions.** That includes all four that aren't correct: both refusals refused three times, and both incorrect answers gave the same figure three times.
- **Two of three agreed on 7, and all three differed on 2.** In five of these nine splits, one answer's first figure was a percentage and another's wasn't: the answers led with different quantities (an operand in one, the result in another), so the vote compared unlike figures.
- **The vote kept a sampled answer twice** (questions 03838 and 07507); both answers were correct before and after. The other 31 kept answers are the stored answers themselves.

**Cost**, at list prices, for the 33 questions:

| | Tokens in / out | Cost |
|---|---|---|
| The stored answers, gpt-oss-120b | 150,739 / 19,415 | $0.034, or $0.0010 a question |
| Two samples each, gpt-oss-120b | 270,836 / 37,404 | $0.063, or $0.0019 a question |

Voting with k = 3 nearly triples a figure answer's cost (2.8 times).

## Comparison

A paired permutation test against the doc agent's first answers:

| Measure | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Correct, metrics-generated | 33 | 0.000 (0.000 to 0.000) | 1.00 |

## Decision

Don't adopt it.

- **There is no gain to pay for.** The doc agent's figure errors on dev are systematic: an answer that is wrong at temperature 0 is wrong the same way at 0.7, so the majority repeats the error rather than outvoting it. Self-consistency helps when mistakes are scattered slips, and these aren't.
- **The copilot sends figure questions elsewhere.** The router gives questions about database measures to the data agent, whose SQL answered 32 of the 33 correctly ([report](data-agent-financebench.md)), so the doc agent writes few figure answers in the copilot.
- **The price is real:** 2.8 times the answer's cost on every figure question it would cover.

**Limits:** 33 questions, of which only four leave room to improve; k = 3 is the smallest useful vote; and the first figure an answer gives isn't always the one the question asks for, so a vote on the asked-for figure, or a larger k, could behave differently. The run's records keep each sample's figure, not its text, so the split votes weren't judged answer by answer. The held-out test split stays closed.

## Logs

- Run: [`eval/results/correctness/doc-agent-v4-sc3--qwen3.8-27b-p2/dev/`](../../eval/results/correctness/doc-agent-v4-sc3--qwen3.8-27b-p2/dev/): question ids, verdicts and metrics only.
- The kept answers, with each vote's figure, the share that agreed and the samples' tokens: `data/processed/answers/doc-agent-v4-sc3/dev/answers.jsonl` (local: FinanceBench's licence keeps answers to its questions out of the repository).
- Reproduce ([runbook](../runbooks/running-evaluations.md)):

  ```bash
  uv run poe self-consistency --source doc-agent-v4-full --k 3 --run doc-agent-v4-sc3
  uv run poe judge-answers --run doc-agent-v4-sc3
  uv run poe compare-runs eval/results/correctness/doc-agent-v4-full--qwen3.8-27b-p2/dev eval/results/correctness/doc-agent-v4-sc3--qwen3.8-27b-p2/dev --metric correct --where question_type=metrics-generated
  ```
