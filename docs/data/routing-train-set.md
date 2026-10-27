# Data card: router training set

| | |
|---|---|
| **What it is** | 2,291 questions written by an LLM, each labelled with a route by the LLM router as the teacher |
| **Files** | [`data/reference/routing_train.jsonl`](../../data/reference/routing_train.jsonl) (one question a line: id, question, the teacher's route, the route the writer was asked for, the style, the teacher's reason, the split) and [`routing_train_manifest.json`](../../data/reference/routing_train_manifest.json) (counts, the leak check, tokens, cost and a checksum) |
| **Licence** | MIT, like the rest of the repository; written for this project, with no FinanceBench text |
| **Built** | 2026-10-27, with `uv run poe generate-routing-train --per-route 400 --pause 0.3` |
| **Used for** | Training the classifier router in Phase 7 (step 7.2). The [routing set](routing-set.md) stays for evaluation |

## How it was built

1. **Writing.** gpt-oss-120b (on Cerebras) wrote 15 questions a batch at temperature 0.9, 27 batches a route. Each batch named six companies from the universe, four of the facts database's measures and one of five styles: terse, casual, formal, with a typo, or with a sentence of context. About a third of each batch were close calls near another route's border (writer prompt w2; a first trial, prompt w1, wrote only clear cases).
2. **Filtering.** Of 2,430 questions, 38 were exact repeats and 24 near-duplicates (bge-small cosine similarity of 0.95 or more to an earlier question). 77 more came within 0.85 of a routing-set question, dev or test, and were dropped, so no training question is a rewording of an evaluation question. The test split was read for this check only: no text of it was printed, and nothing was scored on it.
3. **Labelling.** The LLM router as deployed (prompt r1 on gpt-oss-120b) labelled every kept question; its label is the one the classifier learns. Before labelling, the same teacher routed all 138 routing-set dev questions correctly on this provider, as on Groq ([ADR-0017](../decisions/0017-routing.md), [ADR-0024](../decisions/0024-second-provider.md)).
4. **Split.** A tenth of each route, chosen at random with a fixed seed, is the validation split the training run selects its epoch on.

## Contents

| Route | Questions | Writer's route kept by the teacher |
|---|---|---|
| doc | 402 | 395 of 400 |
| data | 381 | 381 of 382 |
| hybrid | 417 | 399 of 399 |
| brief | 385 | 384 of 395 |
| smalltalk | 304 | 304 of 321 |
| decline | 402 | 393 of 394 |
| **All** | **2,291** (2,062 train, 229 validation) | **2,256 of 2,291** |

- **Closeness to the routing set,** by the highest cosine similarity of each kept question to any routing-set question: median 0.744, 95th percentile 0.821, at most 0.85.
- **Cost:** $0.12 to write (99,111 tokens in, 107,329 out) and $0.90 to label (2,003,218 in, 266,554 out), at list prices.

## Known issues

- **Written and labelled by models.** The questions are an LLM's idea of what users ask, and the labels are the teacher's; neither was read by a person. The teacher makes no mistakes on the routing set, but its labels here are unchecked beyond that.
- **The teacher's 35 relabels** mostly moved questions written as small talk or a brief to another route; they are kept with the teacher's label, which is what the classifier is meant to copy.
- **One provider's teacher.** The labels come from gpt-oss-120b on Cerebras; on the routing set it routes exactly as on Groq.
