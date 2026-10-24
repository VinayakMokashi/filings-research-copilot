# Routing: semantic and LLM routers

Phase 5, step 5.2. Routing set dev, 138 questions; the held-out test split was not opened.

## Question

Every question passes through the router before anything else, so its accuracy caps the copilot's, and its latency and cost are paid on every question, small talk included. Which router should choose among the six routes: one that compares the question with labelled examples by embedding similarity, one that asks a model, or a cascade of the two? And what does each cost?

## Setup

- **Questions:** the [routing set](../data/routing-set.md)'s dev side: 138 questions from 46 hand-written seeds, each seed with two reviewed paraphrases. By route: `doc` 30, `data` 30, `hybrid` 21, `brief` 18, `smalltalk` 18, `decline` 21. The test side (60 questions from 20 other seeds) stays closed until Phase 5's milestone.
- **Floors:** the majority route (always `doc`) and the keyword rules written with the set. The rules were written while reading the seeds, so they score 0.957 on the dev seeds and 0.457 on the paraphrases.
- **Semantic router** ([guide](../concepts/semantic-routing.md)):
  - examples: the dev questions themselves, embedded with `BAAI/bge-small-en-v1.5` on the laptop CPU;
  - **evaluated leaving one seed group out:** each question is routed with its own seed and paraphrases removed from the examples, because a question's own paraphrases sit at a median similarity of 0.936 to it, against 0.707 for the closest question from another seed;
  - variants: a similarity-weighted vote of the k nearest examples (k = 1, 5 or 10), with or without bge's search instruction, or the nearest route centroid; and with or without masking company names and years. **The vote of five, unmasked, was the design chosen before any run**; the other variants were tried after it, on the same questions.
- **LLM router** (prompt `r1`): the six route definitions, the routing set's labelling rules, the 28 measures the facts database holds, and 13 example questions written for the prompt. Every example was checked against all 198 routing-set questions by embedding similarity, by number only: two first drafts came within 0.91 of test questions and were replaced, and the closest left is 0.78, to a dev question. JSON mode, temperature 0, cached. Run on three models:
  - `groq/openai/gpt-oss-20b`, the smallest and cheapest per token;
  - `groq/openai/gpt-oss-120b`, the gateway's `strong` role and the answer model;
  - `groq/qwen/qwen3.8-27b`, the gateway's `fast` role.
- **Measures:** accuracy with a 95% bootstrap interval, or the exact binomial interval when every answer is right, since a bootstrap interval then collapses to a point; paired permutation tests against the keyword rules, Holm-adjusted across the routers compared ([ADR-0007](../decisions/0007-evaluation-statistics.md)); latency per question (for the semantic router, embedding and deciding on the laptop CPU; for the LLM router, the model call as Groq served it); tokens; and cost at list prices.

## Results

| Router | Accuracy (95% interval) | Seeds | Paraphrases | Latency, median / 95th percentile | Tokens | Cost a question |
|---|---|---|---|---|---|---|
| Majority (always `doc`) | 0.217 (0.152 to 0.290) | 0.217 | 0.217 | | | |
| Keyword rules | 0.623 (0.543 to 0.703) | 0.957 | 0.457 | under 1 ms | none | none |
| Semantic, a vote of five, as first designed | 0.391 (0.312 to 0.471) | 0.348 | 0.413 | 8 ms / 12 ms | none | none |
| Semantic, masked, nearest centroid | 0.739 (0.667 to 0.812) | 0.739 | 0.739 | 8 ms / 13 ms | none | none |
| LLM, gpt-oss-20b | 0.964 (0.928 to 0.993) | 0.957 | 0.967 | 0.68 s / 1.16 s | 997 | $0.00010 |
| **LLM, gpt-oss-120b** | **1.000 (exact 0.974 to 1.000)** | 1.000 | 1.000 | 0.51 s / 1.14 s | 970 | $0.00019 |
| LLM, Qwen3.8 27B | 1.000 (exact 0.974 to 1.000) | 1.000 | 1.000 | 0.33 s / 1.59 s | 859 | $0.00080 |

The semantic variants, all evaluated the same way:

| Semantic router | Accuracy (95% interval) | Seeds | Paraphrases |
|---|---|---|---|
| Vote of 1 | 0.319 (0.246 to 0.399) | 0.304 | 0.326 |
| **Vote of 5, the design chosen first** | **0.391 (0.312 to 0.471)** | 0.348 | 0.413 |
| Vote of 10 | 0.442 (0.362 to 0.522) | 0.457 | 0.435 |
| Vote of 5, with the search instruction | 0.355 (0.275 to 0.435) | 0.283 | 0.391 |
| Nearest centroid | 0.543 (0.457 to 0.630) | 0.587 | 0.522 |
| Vote of 5, companies and years masked | 0.522 (0.435 to 0.609) | 0.522 | 0.522 |
| **Nearest centroid, companies and years masked** | **0.739 (0.667 to 0.812)** | 0.739 | 0.739 |

By route:

| Router | doc | data | hybrid | brief | smalltalk | decline |
|---|---|---|---|---|---|---|
| Keyword rules | 0.67 | 0.70 | 0.43 | 0.72 | 0.67 | 0.52 |
| Semantic, a vote of five | 0.17 | 0.57 | 0.05 | 0.39 | 0.83 | 0.43 |
| Semantic, masked, nearest centroid | 0.80 | 0.87 | 0.62 | 0.78 | 0.83 | 0.48 |
| LLM, gpt-oss-20b | 1.00 | 1.00 | 1.00 | 0.94 | 0.89 | 0.90 |
| LLM, gpt-oss-120b | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| LLM, Qwen3.8 27B | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Each run's confusion matrix is in its folder, for example [gpt-oss-20b's](../../eval/results/routing/llm-gpt-oss-20b/dev/confusion.md).

### Why the first semantic design failed

A question's nearest examples shared its company or its metric, not its route. "Which competitors does AMD name in its annual report?" (`doc`) was closest to five questions about AMD's R&D spending (`data` and `hybrid`); "What does Coca-Cola say about its relationship with its bottling partners?" (`doc`) to three memos comparing Coca-Cola and PepsiCo (`brief`); "Did Boeing's revenue recover after 2020, and what reasons does its 10-K give?" (`hybrid`) to five questions that ask for one figure (`data`). Generic embeddings measure what a question is about, and a route depends on what it asks.

Two changes address that, and each helps on its own:

- **Masking** the company names (as "Acme") and years (as "2020") removes the strongest topical signal: the vote of five rises from 0.391 to 0.522.
- **Centroids** average each route's 15 to 30 examples, which washes out the topics the examples happen to share and keeps what they have in common: 0.391 to 0.543 unmasked.

Together they reach 0.739. These were chosen on dev after seeing the first design's errors, so the test split, opened once at the milestone, will say how much of the gain holds.

The masked-centroid router still confuses the routes the LLM router has to separate by reading: `hybrid` questions go to `data` (7 of 21), because the figure is the most similar part, and `decline` goes to `smalltalk` (8 of 21), because "Write a poem about the ocean" and "What can you help me with?" are both requests to the assistant. Its confusion matrix is [here](../../eval/results/routing/semantic-masked-centroid/dev/confusion.md).

### Where the LLM routers differ

On the 81 `doc`, `data` and `hybrid` questions, the borders that decide which agent answers, every LLM router was right every time. They differ only on the rest:

| Question (route) | gpt-oss-20b | gpt-oss-120b | Qwen3.8 27B |
|---|---|---|---|
| "Which companies do you cover?" and a paraphrase (`smalltalk`) | `doc`: "a disclosure request" | right | right |
| "Write a poem about the ocean" and a paraphrase (`decline`) | `brief`: "creative writing request" | right | right |
| "Overview of Amazon's 2022 performance: revenue, profitability, risks, and outlook." (`brief`) | `hybrid` | right | right |

gpt-oss-20b read "cover" as asking which companies a filing discloses, and a poem as a written deliverable. Both readings are defensible word by word, and both would send a first-time user somewhere odd.

### A cascade

The semantic router's confidence is its margin: how much closer the nearest route centroid is than the next. Letting it decide when the margin is large, and asking gpt-oss-120b otherwise, gives on dev:

| Margin needed | Semantic decides | Its accuracy there | Cascade accuracy | LLM calls saved |
|---|---|---|---|---|
| (always the LLM) | none | | 1.000 | none |
| 0.10 | 6 (4%) | 1.000 | 1.000 | 4% |
| 0.08 | 12 (9%) | 1.000 | 1.000 | 8% |
| 0.05 | 25 (18%) | 0.960 | 0.993 | 17% |
| 0.03 | 48 (35%) | 0.875 | 0.957 | 34% |

Computed from the two runs' decisions, which is what a cascade run would make since both routers are deterministic and the model calls are cached. The thresholds are read off dev, so they flatter the cascade.

## Comparison

Against the keyword rules, paired permutation tests, Holm-adjusted across the four routers compared ([family](../../eval/results/routing/_comparisons/routers-vs-keyword.md)):

| Router | Accuracy | Difference (95% interval) | p | Holm p |
|---|---|---|---|---|
| Semantic, masked, nearest centroid | 0.739 | +0.116 (+0.007 to +0.225) | 0.051 | 0.051 |
| LLM, gpt-oss-20b | 0.964 | +0.341 (+0.261 to +0.427) | 0.0001 | 0.0004 |
| LLM, gpt-oss-120b | 1.000 | +0.377 (+0.297 to +0.457) | 0.0001 | 0.0004 |
| LLM, Qwen3.8 27B | 1.000 | +0.377 (+0.297 to +0.457) | 0.0001 | 0.0004 |

Between the routers that matter for the decision:

- **gpt-oss-120b against gpt-oss-20b:** +0.036 (+0.007 to +0.072), p = 0.057. All five questions they disagree on favour gpt-oss-120b, but five questions from three seeds can't settle it on their own.
- **gpt-oss-120b against the masked-centroid semantic router:** +0.261 (+0.188 to +0.333), p = 0.0001. gpt-oss-120b gets 36 questions the semantic router misses, and misses none it gets.
- **Qwen3.8 27B against gpt-oss-120b:** no difference; both routed every question correctly.

On paraphrases only, the 92 questions the keyword rules weren't written on, the masked-centroid router beats them by +0.283 (+0.152 to +0.413), p = 0.0001; the vote of five, as first designed, doesn't differ from them there (-0.043, p = 0.63).

## Decision

Route with the LLM router on gpt-oss-120b, the `strong` role, and keep the masked-centroid semantic router beside it as the fallback when the call fails ([ADR-0017](../decisions/0017-routing.md)):

- **It routed every dev question correctly,** at $0.00019 and 0.51 s at the median.
- **gpt-oss-20b costs half as much** but misroutes the questions a first-time user is most likely to ask, about what the copilot covers and what it won't do; the difference isn't significant on dev, and the cost difference is $0.00009 a question.
- **Qwen3.8 27B** routed every dev question correctly too, faster at the median (0.33 s) but slower at the 95th percentile (1.59 s), at four times the cost ($0.00080); it buys nothing gpt-oss-120b doesn't.
- **The semantic router** can't route on its own (0.739), but as a fallback it keeps the copilot answering when the model's quota runs out, and it costs nothing to run beside the LLM. A semantic-first cascade would save 8% to 17% of the router calls on dev, $0.00003 a question at most, at thresholds read off dev; the larger saving already costs a misroute.

The test split, with seeds no prompt example or design choice has seen, is opened once at Phase 5's milestone.

## Logs

- Runs: `eval/results/routing/<run>/dev/`, each with `items.jsonl` (the route, the prediction, the confidence or the model's reason, latency, tokens and cost per question), `summary.md` and `confusion.md`; the family of paired tests in [`eval/results/routing/_comparisons/`](../../eval/results/routing/_comparisons/).
- Decisions as they were made, and the model calls: `data/processed/routing/<run>/dev/decisions.jsonl` and `data/cache/router.jsonl` (local, not committed).
- Reproduce ([runbook](../runbooks/running-evaluations.md)):

  ```bash
  uv run poe run-router --router semantic --mask entities --method centroid --run semantic-masked-centroid
  uv run poe run-router --router llm --role strong --run llm-gpt-oss-120b
  FRC_LLM_FAST_MODEL=groq/openai/gpt-oss-20b uv run poe run-router --router llm --run llm-gpt-oss-20b
  uv run poe run-router --router llm --run llm-qwen3.8-27b
  ```
