# Hybrid answers: a prototype on thirteen questions

Phase 4, step 4.6. Questions written for this project, on dev companies; no held-out data was used.

## Question

Can one answer take its figures from the data agent and its explanation from the filings, citing each to where it came from? And how does that compare with the doc agent alone on questions that need both?

## Setup

- **Questions:** the [hybrid set](../data/hybrid-set.md), 13 questions on 9 dev companies. The first ten ask about two years that one filing states side by side; one of them (h10) asks for a segment figure the database doesn't hold. h11 to h13 were added after the first run: they ask for five years, and a middle year is in no filing in the corpus, or only deep in one.
- **Hybrid agent** (`hybrid-v1`, [guide](../concepts/hybrid-answers.md)):
  - the data agent with the figures hint, its query result as source [1];
  - the doc agent's retrieval, pages [2] onwards within 3,000 tokens;
  - one `groq/openai/gpt-oss-120b` answer under the hybrid rules (prompt v1), with no retry.
- **Doc agent alone** (`doc-agent-v4`): the Phase 3 agent, unchanged, with its one retry ([report](doc-agent-dev.md)).
- **Checks:**
  - figures: each expected figure within 1% at any scale, against formulas over the facts database;
  - citations: whether an answer cites the query result, and a page;
  - faithfulness: the Qwen judge (`qwen3.8-27b`, prompt 1) checks each sentence against the sources it cites;
  - explanation: each answer read by hand against what its question asks to be explained ([hybrid review](../../eval/results/hybrid/hybrid-v1/dev/review.json), [doc agent review](../../eval/results/hybrid/doc-agent-v4/dev/review.json)).
- **Tests:** paired permutation tests over the 13 questions ([ADR-0007](../decisions/0007-evaluation-statistics.md)). With 13 questions, only a large difference could show.

## Results

| Measure | Hybrid | Doc agent alone |
|---|---|---|
| Answered | 10 of 13 | 10 of 13 |
| Gave every expected figure | 10 | 10 |
| Explained, read by hand | 9 | 9 |
| Every sentence supported by its citations | 8 | 6 |
| Share of sentences supported | 0.72 | 0.67 |
| Cited the query result | 9 | |
| Tokens a question | 9,701 | 7,318 |
| Model time, median | 7.0 s | 5.0 s |
| Cost a question at list prices | $0.0048 | $0.0030 |

By group of questions:

| Group | Hybrid | Doc agent alone |
|---|---|---|
| Two years that one filing states (h01 to h09) | 9 answered, every figure | 9 answered, every figure |
| A segment figure the database doesn't hold (h10) | Refused | Answered, after its retry |
| Five years, a middle year missing from the corpus (h11 to h13) | 1 answered; the query held all five years for all three | 0 answered |

Question by question:

| ID | Question | Hybrid | Doc agent alone |
|---|---|---|---|
| h01 | 3M's capital expenditure, 2017 to 2018 | Figures from the query; explains | Figures from the pages; explains |
| h02 | Coca-Cola's net income, 2016 to 2017 | Explains | Explains; one sentence unsupported |
| h03 | Walmart's operating income | Explains | Explains |
| h04 | Nike's revenues | Explains; one sentence unsupported | Explains; one sentence unsupported |
| h05 | MGM Resorts' revenue | Explains | Explains |
| h06 | Boeing's revenue, with 2017 restated | Both 2017 figures, but not which is restated; one sentence unsupported | The restated figure; explains |
| h07 | Adobe's revenue | Figures from the pages, as the data agent declined; explains | Explains |
| h08 | Block's revenue | Explains | Explains |
| h09 | General Mills's free cash flow | The figure, but no explanation | The figure, but no explanation |
| h10 | Boeing Commercial Airplanes revenue | Refused | Figures and explanation, after its retry |
| h11 | 3M's capital expenditure, 2018 to 2022 | All five years from the query; explains | Refused: 2019 and 2020 missing |
| h12 | Coca-Cola's net income, 2017 to 2021 | Refused, with all five years from the query | Refused: 2018 missing |
| h13 | Boeing's revenue, 2018 to 2022 | Refused, with all five years from the query | Refused: 2019 missing |

## Comparison

Neither agent answers more questions than the other: both answer 9, the doc agent alone answers h10, the hybrid alone h11, and neither h12 or h13. Every-sentence support is +0.15 for the hybrid (−0.15 to +0.46), p = 0.63. No difference is significant on 13 questions.

What the numbers hide is where each one fails:

- **The hybrid refuses with the figures in hand.** For h10, h12 and h13 it had every figure: from a page for h10, from the query for h12 and h13. No retrieved page explained the change, and the rules allow only a full answer or a refusal, so it refused. The doc agent's retry found h10's explanation on PDF page 43; the hybrid has no retry.
- **The doc agent can't reach years its filings don't hold.** On h11 to h13 it named the missing years and refused. The data agent supplied all of them, including 3M's and Boeing's 2019 figures, which appear in no filing in the corpus.
- **On two-year questions they tie.** When one filing states both years beside the explanation, the doc agent finds the figures on the page it needs anyway. The hybrid adds the citation to the query, an exact provenance for each figure, and costs about 60% more.

## Error analysis

| Problem | Questions | What it looks like |
|---|---|---|
| A refusal when the figures were there but no explanation | h10, h12, h13 (hybrid) | Missing: "Narrative explanation in the 2021 Form 10-K of the factors that drove Coca-Cola's 2021 net income result" |
| The explanation's page not retrieved | h09 (both) | The cash-flow discussion is on PDF page 27; pages 26 and 28 were retrieved |
| The data agent declined for the narrative half | h07 (hybrid) | "The database ... does not store qualitative commentary or explanations for revenue growth"; the figures came from the pages |
| A change written twice | h11 (hybrid), h01 (doc agent) | "an increase of $122 million from 2018 to 2019 122,000,000": the model's own figure, then the calculator's |
| A computed figure outside the calculator | h06 (hybrid) | "the combined segment growth of roughly $7.8 billion", summed by the model, so the judge can't support it |
| A long sentence that says more than its pages | h04 (both) | Ranges and regional contributions packed into one sentence |
| A restated figure given without its label | h06 (hybrid) | $93,392 million and $94,005 million for 2017, without saying the second is the restatement |

h10 also checks the data agent: it declined rather than offer Boeing's total revenue as the segment's, though it gave the narrative half as its reason, not the missing segment figures.

## Decision

- **Phase 4's exit test is met.** The plan asks for "the hybrid prototype handles 10 hand-picked questions". It answered 10 of the 13 with every expected figure and explained 9. On the questions it exists for, figures from years the corpus filings don't hold, it alone had the figures.
- **What Phase 5 takes from it,** in order of the failures each would fix:
  1. **Partial answers.** Give the figures and say what the sources don't explain, instead of refusing (h10, h12, h13).
  2. **The retry.** Search again for what an answer says is missing, as the doc agent does; it found h10's explanation.
  3. **A planner that splits the question,** figures to the data agent and reasons to the doc agent, instead of a hint the data agent can ignore (h07).
  4. **Routing by need.** A question about years that one filing states can go to the doc agent alone, at about 60% of the cost.
  5. **Each computed figure written once,** by the calculator (h01, h06, h11).
- **No change to either agent now.** A prototype on 13 questions written by the same project is evidence for Phase 5's design, not a basis for tuning.

## Logs

| What | Where |
|---|---|
| Hybrid: checks per question, answers (without page text), review | [`eval/results/hybrid/hybrid-v1/dev/`](../../eval/results/hybrid/hybrid-v1/dev/summary.md) |
| Doc agent alone | [`eval/results/hybrid/doc-agent-v4/dev/`](../../eval/results/hybrid/doc-agent-v4/dev/summary.md) |
| The questions and expected figures | [`eval/hybrid/questions.jsonl`](../../eval/hybrid/questions.jsonl) ([data card](../data/hybrid-set.md)) |

To reproduce them:

```bash
uv run poe run-hybrid --agent hybrid --run hybrid-v1     # needs Qdrant, the facts database and GROQ_API_KEY
uv run poe run-hybrid --agent doc --run doc-agent-v4
R=eval/results/hybrid
uv run poe compare-runs $R/doc-agent-v4/dev $R/hybrid-v1/dev --metric all_figures
```

The answers with their sources' text and the judge's sentence-by-sentence checks stay in the local `data/processed/hybrid/` folder.
