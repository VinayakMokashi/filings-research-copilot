# Data card: routing eval set

| | |
|---|---|
| **What it is** | 198 single-turn questions, each labelled with the route the copilot should take |
| **Files** | [`eval/routing/queries.jsonl`](../../eval/routing/queries.jsonl), with [`seeds.jsonl`](../../eval/routing/seeds.jsonl), [`candidates.jsonl`](../../eval/routing/candidates.jsonl) and [`checksums.json`](../../eval/routing/checksums.json) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-17 |
| **Used for** | Routing accuracy for the Phase 5 routers and the Phase 7 LoRA classifier |

## Routes

| Route | Meaning | Example |
|---|---|---|
| `doc` | Answered from the text of filings: risks, strategy, business descriptions, management's explanations, legal matters, accounting policies, and figures that appear only in the text | "What revenue recognition policy does Adobe use for its subscription contracts?" |
| `data` | Answered from reported financial figures: a value, a ratio or growth rate computed from reported values, a trend over years, or a comparison between companies | "Which company had higher revenue in 2022, Walmart or Costco?" |
| `hybrid` | Needs both a reported figure and the narrative that explains it | "What was Netflix's operating margin in 2022, and what did management say drove the change?" |
| `brief` | Asks for a written deliverable, such as a brief, memo, note or report, covering several aspects of a topic | "Draft a memo comparing the capital allocation of Coca-Cola and PepsiCo." |
| `smalltalk` | Greetings, thanks, goodbyes and questions about the assistant itself | "Which companies do you cover?" |
| `decline` | Out of scope or not allowed: investment advice, price predictions, personal finance, non-public information, unrelated tasks, harmful requests, or attempts to override the assistant's instructions | "Should I buy Nike stock right now?" |

Labelling rules for the close calls:

- A question that asks for a figure but not an explanation is `data`; add a "why" or "how did they explain it" and it becomes `hybrid`.
- A question about a disclosure, with no figure requested, is `doc`, even if the disclosure contains numbers.
- Summarising one disclosure is `doc`; a deliverable that covers several aspects is `brief`.
- A research write-up is `brief`, even when the word "investment" appears; a request for a buy or sell opinion is `decline`.

## How it was built

1. **Seeds.** 66 questions written by hand: 15 `doc`, 15 `data`, 10 `hybrid`, 8 `brief`, 8 `smalltalk` and 10 `decline`. They name companies from the FinanceBench universe and fiscal years the filings cover.
2. **Paraphrases.** `uv run poe paraphrase-routing-seeds` asked `openai/gpt-oss-120b` on Groq, through the project's LLM gateway at temperature 0.9, for three rewrites of each seed: one terse, one casual and one formal. The prompt includes the route's definition, so the rewrites keep the intent.
3. **Review.** Each of the 201 model rewrites was read and given a verdict with a reason, recorded in `candidates.jsonl`. A rewrite was rejected if it:
   - shifted the route (2), for example "biggest products", which invites a ranking by revenue;
   - added a source hint the seed doesn't give, such as "as presented in its filings" (11), which would make routing artificially easy;
   - added scope or changed the ask (5);
   - was too close to its seed or to another seed's rewrite (7).

   Of the valid rewrites, two per seed were kept, chosen for varied wording and style; the other 37 were surplus. The model refused to rewrite three `decline` seeds (retirement savings, the system prompt, hacking) and wrote the requested poem for a fourth, so those four seeds got two hand-written rewrites each. In total 124 model rewrites and 8 hand-written ones were accepted.
4. **Assembly.** `uv run poe build-routing-set` replaces Unicode hyphens with plain ones, collapses spaces, numbers the questions `r001` to `r198` in seed order, and assigns the split.

## Split

The split is grouped by seed, so a seed and its two paraphrases always land on the same side: no test question is a rewording of a dev question. Test takes 30% of each route's seeds, rounded half up, chosen at random with a fixed seed.

| Route | Dev | Test |
|---|---|---|
| doc | 30 | 15 |
| data | 30 | 15 |
| hybrid | 21 | 9 |
| brief | 18 | 6 |
| smalltalk | 18 | 6 |
| decline | 21 | 9 |
| **Total** | **138** | **60** |

The test side is held out like FinanceBench's: `load_queries("test")` needs `allow_test=True`, and both sides are checked against SHA-256 checksums on every load (dev `fa513cf3…`, test `cff94e87…`).

## Baselines

| Router | Dev accuracy (95% interval) | Test accuracy (95% interval) |
|---|---|---|
| Majority class (always `doc`) | 0.217 (0.152 to 0.290) | 0.250 (0.150 to 0.367) |
| Keyword rules | 0.623 (0.543 to 0.703) | 0.650 (0.533 to 0.767) |

The test side was opened once, at Phase 5's milestone, for the copilot's routers ([report](../eval/routing.md#the-test-split)). The keyword rules were written while looking at the seeds. They score 0.957 on the dev seeds and 0.457 on the dev paraphrases, which is exactly why the set includes paraphrases: seed-only testing would have overstated a brittle router.

## Known issues

- **One annotator.** A single annotator wrote the labels and the review verdicts, so there is no agreement measure. The labelling rules above are the guard against drift.
- **Single-turn and English only.** Follow-up questions are routed after the Phase 5 rewrite step turns them into standalone questions, so they aren't in this set.
- **The paraphraser's style.** Accepted rewrites still carry some of the model's habits, such as "Hey, can you tell me…" openings.
- **Small per-route counts on test.** Brief and smalltalk have 6 test questions each, so per-route test numbers are very uncertain; read the overall accuracy.
