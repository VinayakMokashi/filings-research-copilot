# The brief crew

Phase 7, step 7.6. The project's brief set: 12 requests on dev companies, each with a rubric; graded by the evaluation's judge, and checked sentence by sentence against the sources.

## Question

Until now the copilot answered a request for a brief with a note to ask one part at a time. Does a crew (a Self-Discover plan, the specialists writing its sections in parallel, the validator's checker as the critic, and an editor) write briefs that cover what the request asks for, with sentences their sources support, better than the copilot's single agents answering the whole request at once?

## Setup

- **The brief set** ([data card](../data/brief-set.md)): 12 requests written for this project, one each for 12 dev companies and none of the test split's, each about a 10-K in the corpus, with a rubric of four or five items that name what the request asks for.
- **Systems,** all on the same models (the strong and fast roles on Cerebras, the critic on Groq's gpt-oss-20b) and the same critic:
  - **the crew** (`copilot.agents.brief`), as the copilot's brief route runs it;
  - **the hybrid, one shot:** the hybrid agent answering the whole request, its answer checked and cut by the same critic;
  - **the doc agent, one shot:** likewise.
- **Measures** (`poe run-briefs`): the rubric score (the share of items the judge says a brief covers; the judge is Qwen3.8 27B on the `fast` role, which writes none of the briefs), the share of sentences the faithfulness check supports against the sources they cite (the same model, as for answers), the brief's length, its distinct sources, its cost and its time. Paired permutation tests over the 12 briefs ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

### The crew

| Measure | Mean (95% interval) |
|---|---|
| Rubric items covered | **0.863** (0.754 to 0.963) |
| Sentences supported | **0.916** (0.859 to 0.962) |
| Briefs with every sentence supported | 0.333 (0.083 to 0.583) |
| Distinct sources cited | 7.1 |
| Length | 411 words |
| Cost | $0.015 a brief |
| Time | 91 seconds a brief |

Seven of the 12 briefs cover every item. Of 43 planned sections, 40 were answered: the critic cut 10 sentences across the set and emptied one section, and two came back unanswered. The three weakest briefs show the crew's three failure modes:

- **A section the critic empties.** Coca-Cola's profitability section lost all three of its sentences to the check, so the brief names it as not covered (rubric 0.50).
- **A module adapted badly.** For JPMorgan the planner adapted the liquidity module as a non-financial company's (cash, debt, credit facilities) instead of a bank's capital ratios, and the section went unanswered (0.50).
- **A list the doc agent won't give.** Adobe's "list the main risk factors" section came back as a refusal (0.75).

### Against the doc agent in one shot

The hybrid answers a question about one company and one year with the doc agent alone (its route by need, step 5.1), and every request here is one, so its one-shot briefs are the doc agent's, word for word: the two baselines are one system.

| Measure | One shot | Crew | Difference (95% interval) | p |
|---|---|---|---|---|
| Rubric items covered | 0.658 (0.442 to 0.854) | 0.863 (0.754 to 0.963) | +0.204 (−0.046 to +0.475) | 0.18 |
| Sentences supported | 0.764 (0.542 to 0.958) | 0.916 (0.859 to 0.962) | +0.152 (−0.042 to +0.372) | 0.22 |
| Requests answered | 10 of 12 | 12 of 12 | | |
| Distinct sources | 3.0 | 7.1 | +4.1 (+2.7 to +5.6) | 0.0008 |
| Length | 97 words | 411 words | +314 (+218 to +414) | 0.0005 |
| Cost | $0.004 | $0.015 | | |
| Time | 40 s | 91 s | | |

On rubric coverage the crew leads by 0.20, a lead 12 briefs can't tell from chance (p = 0.18). It covers more in five briefs, ties in four and covers less in three: JPMorgan and Coca-Cola, where a section went unanswered or was emptied, and Walmart. The one shot refused two requests outright (Nike and Verizon); among the ten it answered, its sentences are supported as often as the crew's (0.917 against 0.929), so the crew's lead on faithfulness comes from answering every request, not from truer sentences. What the crew adds for certain is breadth: more than twice the sources, and a brief of three or four sections rather than an answer of four sentences, for 3.5 times the cost.

A second judge, gpt-oss-120b (`poe jury-briefs`), agrees with the first on 98% of the one shot's rubric items (kappa 0.96) and 95% of the crew's (kappa 0.70). It scores the crew's items a little higher than the first judge does (0.92 against 0.88), and it is the model that writes the crew's sections, so the first judge's lower reading is the one reported.

## Decision

**Adopt the crew as the copilot's brief route** ([ADR-0030](../decisions/0030-brief-crew.md)). The route had no implementation until now: a request for a brief got a note. Against the doc agent answering the request in one shot, the crew answers every request, cites more than twice the sources and covers 0.20 more of what the requests ask for, a lead 12 briefs can't establish as significant; it costs 3.5 times as much and takes twice as long. Its three failure modes are where a next version starts: a revision before a section is cut, modules adapted by industry, and a doc agent that will give a list.

**Limits:** 12 briefs written for this project, so small effects can't show; one judge for the headline, with a second agreeing on 95% of the crew's items; the critic runs on Groq's free tier, whose daily quota a set of 12 briefs nearly fills; the crew and the one shot share every model and the critic, so the comparison is of the design alone.

## Logs

- Grades by brief: [`eval/results/briefs/`](../../eval/results/briefs/) (`crew-v1`, `hybrid-one-shot`, `doc-one-shot`), with each brief's text and rubric verdicts; the briefs with their sources' text stay in `data/processed/briefs/` (git-ignored).
- Reproduce (the strong and fast roles on Cerebras; the critic stays on Groq):

  ```bash
  FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b \
  FRC_LLM_TOKENS_PER_MINUTE=25000 uv run poe run-briefs --system crew --run crew-v1
  uv run poe run-briefs --system hybrid --run hybrid-one-shot
  uv run poe run-briefs --system doc --run doc-one-shot
  uv run poe compare-runs eval/results/briefs/hybrid-one-shot/dev eval/results/briefs/crew-v1/dev --metric rubric
  ```
