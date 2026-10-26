# Self-consistency

> Ask for the same figure several times, sampling; keep the one most answers agree on.

**Lands in:** Phase 5 · **Code:** `src/copilot/answer/consistency.py`; `scripts/self_consistency.py`

## What it is

A model answering at temperature 0 gives its single most likely answer, and when that answer is wrong, asking again gives the same wrong answer. **Self-consistency** (Wang et al., 2023) samples several answers at a higher temperature, so each takes a slightly different path through the same sources, and keeps the answer most of them reach. When errors are scattered and the right answer is the common one, the vote filters out the slips: one sample reads the wrong column of a table, another adds a line the others don't, and both are outvoted.

Its cost is simple: k samples cost k answer calls.

## Why we need it here

The plan asks whether voting improves the copilot's figure answers enough to pay for itself. Two facts frame the answer before any measurement:

- **The router sends figure questions to the data agent**, whose SQL runs at temperature 0 over the facts database and answered 32 of FinanceBench's 33 dev figure questions correctly ([report](../eval/data-agent-financebench.md)). A deterministic query has little to vote on.
- **The doc agent still writes figures** that live only in the text, and the hybrid answer's explanations; on the 33 figure questions it answered 29 correctly from the filings' pages. That is where voting could help.

So the experiment measures the doc agent's figure answers: if voting can't help there, it has no place in the copilot.

## How it works

1. **The votes.** The doc agent's stored answer, written at temperature 0, is the first vote. Each further vote is an answer call over the same numbered sources at temperature 0.7, with its own seed, which also keys it apart from the others in the cache.
2. **The figure.** Each answer's main figure is the first one it gives, read by the answer judge's figure parser, which leaves out bare years and reads "$1,577 million" and "$1.577 billion" as the same figure.
3. **The vote.** Answers whose main figures are within 1% of each other form a group; refusals form a group of their own, and so do answers without a figure. The largest group wins; on a tie, the group that holds the earliest answer, so a split vote keeps the deterministic one.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.answer.consistency.sample` | One answer call at temperature 0.7 with a seed |
| `copilot.answer.consistency.key_figure` | An answer's main figure, or none |
| `copilot.answer.consistency.vote` | The answer to keep and the share that agrees |
| `scripts/self_consistency.py` (`poe self-consistency`) | Votes over a run's stored figure answers, kept as a new run for the judge |

## How we measured it

Two samples were added to each of the doc agent's stored answers to FinanceBench's 33 dev figure questions, and the votes were counted and judged ([report](../eval/self-consistency.md)):

| | Doc agent | Self-consistency, k = 3 |
|---|---|---|
| Correct | 0.879 (0.76 to 0.97) | 0.879 (0.76 to 0.97) |
| Cost of a figure answer | $0.0010 | $0.0030 |

- **No verdict changed** (p = 1.00). The votes agreed on 24 questions, among them all four the doc agent gets wrong or refuses: its figure errors are systematic, so sampling repeats them instead of outvoting them.
- **Where the votes split,** the answers often led with different quantities, a percentage in one and an amount in another, so a vote on the first figure compares unlike things.
- **Decision: not adopted.** The copilot sends figure questions to the data agent, and the doc agent's figure mistakes aren't the scattered kind a vote can fix.

## Review questions

1. Why does sampling at temperature 0 not help, and what does a higher temperature change?
2. Why vote on the figure rather than on the whole answer's wording?
3. Why does the deterministic answer win a tie?
4. Why does routing figure questions to SQL leave self-consistency little to do?

## References

- Wang et al., [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171), 2023.
- [LLM as a judge](llm-as-judge.md) for the figure comparisons the vote reuses.
