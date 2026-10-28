# Data card: brief set

| | |
|---|---|
| **What it is** | 12 requests for research briefs, each with a rubric of four or five items that name what the request asks for |
| **Files** | [`eval/briefs/briefs.jsonl`](../../eval/briefs/briefs.jsonl) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-28 |
| **Used for** | Evaluating the brief crew (step 7.6) against the copilot's single agents |

## Contents

Each record has an `id`, the `company`, the `filing` the brief is chiefly about, the `request` as a user would type it, and the `rubric`. One request a company, for 12 of the 20 dev companies, and none of the 12 test companies, so the held-out split stays untouched ([ADR-0006](../decisions/0006-evaluation-splits.md)); a test checks this. Every filing is a 10-K in the corpus.

| Requests ask for | Count |
|---|---|
| Results (revenue and earnings) | 12 |
| Segments or the revenue mix | 7 |
| Risks, litigation or regulation | 7 |
| Liquidity, debt, cash flow or capital | 7 |
| Capital returns (dividends, buybacks) | 3 |
| Margins, drivers or e-commerce | 7 |

An example: "Write a one-page brief on 3M's fiscal 2022 for an investment committee: results, business segments, litigation exposure and liquidity", with the rubric "States 3M's total net sales for 2022, with a figure"; "Gives 3M's operating income or operating margin for 2022, with a figure"; "Describes how at least two of 3M's business segments performed in 2022"; "Discusses 3M's litigation exposure, such as PFAS-related matters or the Combat Arms earplug lawsuits"; "Covers liquidity: cash, debt or credit facilities".

## How it is graded

The rubric judge (`copilot.eval.briefs`, the evaluation's judge model on the `fast` role) reads a brief and says, item by item, whether it covers what the item asks for: a figure when the item asks for one, a named matter when it names one. It doesn't decide whether the facts are right; the faithfulness check does that, sentence by sentence, against the sources each sentence cites. A brief's rubric score is the share of its items it covers.

## Known issues

- **Coverage, not quality.** A rubric item is met by a brief that states the figure; it says nothing about whether the brief explains it well or reads well.
- **Written from knowledge of the filings.** Some items name matters these 10-Ks are known to discuss (3M's PFAS litigation, CVS Health's opioid litigation); a brief that covers a different, equally real matter is still credited when the item says "such as".
- **Small.** 12 briefs give wide intervals: a difference of a few items between two systems isn't significant.
