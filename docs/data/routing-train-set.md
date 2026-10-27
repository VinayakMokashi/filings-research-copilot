# Data card: router training set

| | |
|---|---|
| **What it is** | 2,328 questions written by an LLM, each labelled with a route by the LLM router as the teacher (version 2 of the set) |
| **Files** | [`data/reference/routing_train.jsonl`](../../data/reference/routing_train.jsonl) (one question a line: id, question, the teacher's route, the route the writer was asked for, the style, the kind of question, the teacher's reason, the split) and [`routing_train_manifest.json`](../../data/reference/routing_train_manifest.json) (counts by route and kind, the leak check by route, tokens, cost and a checksum) |
| **Licence** | MIT, like the rest of the repository; written for this project, with no FinanceBench text |
| **Built** | 2026-10-27, with `uv run poe generate-routing-train --per-route 400 --pause 0.3` (writer prompt w3) |
| **Used for** | Training the classifier router in Phase 7 (step 7.2; [guide](../concepts/lora-classifier.md)). The [routing set](routing-set.md) stays for evaluation |

## How it was built

1. **Writing.** gpt-oss-120b (on Cerebras) wrote 15 questions a batch at temperature 0.9, 27 batches a route. Each batch named six companies from the universe, four of the facts database's measures, one of five styles (terse, casual, formal, with a typo, or with a sentence of context), and **one kind of question its route's definition names, in turn**: the decline route's seven kinds (investment advice, price predictions, personal finance, non-public information, unrelated tasks, harmful requests, attempts to override the instructions), the doc route's seven, the data route's four, the brief route's four deliverables and small talk's four. About a third of each batch were close calls near another route's border.
2. **Filtering.** Of 2,433 questions, 22 were exact repeats and 12 near-duplicates (bge-small cosine similarity of 0.95 or more to an earlier question). 71 more came within 0.85 of a routing-set question, dev or test, and were dropped, so no training question is a rewording of an evaluation question; small talk lost the most (24), since greetings and thanks are alike whoever writes them. The test split was read for this check only: no text of it was printed, and nothing was scored on it.
3. **Labelling.** The LLM router as deployed in Phase 5 (prompt r1 on gpt-oss-120b) labelled every kept question; its label is the one the classifier learns. The same teacher routed all 138 routing-set dev questions correctly on this provider, as on Groq ([ADR-0017](../decisions/0017-routing.md), [ADR-0024](../decisions/0024-second-provider.md)).
4. **Split.** A tenth of each route, chosen at random with a fixed seed, is the validation split the training run selects its epoch on.

## Contents

| Route | Questions | Writer's route kept by the teacher | Kinds |
|---|---|---|---|
| doc | 373 | 363 of 399 | 7, with 44 to 60 questions each |
| data | 409 | 389 of 389 | 4, with 90 to 102 |
| hybrid | 442 | 399 of 399 | 1 |
| brief | 386 | 380 of 399 | 4, with 88 to 105 |
| smalltalk | 326 | 326 of 351 | 4, with 79 to 93 |
| decline | 392 | 383 of 391 | 7, with 44 to 60 |
| **All** | **2,328** (2,095 train, 233 validation) | **2,240 of 2,328** | |

(The kinds count the questions by the route the writer was asked for.)

- **Closeness to the routing set,** by the highest cosine similarity of each kept question to any routing-set question: median 0.745, 95th percentile 0.824, at most 0.849.
- **Cost:** $0.11 to write (100,531 tokens in, 102,618 out) and $0.92 to label (2,036,494 in, 279,790 out), at list prices.

## Version 1

The first version (2,291 questions, writer prompt w2; commit `da7b6f7`) asked for routes, companies, measures and styles, but not for kinds. Its decline questions were almost all requests for investment advice (297 of 402), with none harmful or trying to override the assistant's instructions, and only 3 unrelated tasks. The classifier trained on it routed those to small talk, with high confidence, on the routing set's dev questions: 9 of 21 declines right ([report](../eval/lora-router.md)). Version 2 asks for every kind each route's definition names. The gap was found on the routing set's dev questions, at the level of kinds, so the final classifier was also scored once on the test split.

## Known issues

- **Written and labelled by models.** The questions are an LLM's idea of what users ask, and the labels are the teacher's; neither was read by a person. The teacher makes no mistakes on the routing set, but its labels here are unchecked beyond that.
- **The teacher's 88 relabels** mostly moved questions written as doc, small talk or a brief to another route; they are kept with the teacher's label, which is what the classifier is meant to copy.
- **The teacher is prompt r1.** The copilot's version 2 routes with prompt r2, which adds rules on the database's grain ([ADR-0026](../decisions/0026-copilot-v2.md)); a classifier meant to stand in for it should be trained on r2's labels.
- **One provider's teacher.** The labels come from gpt-oss-120b on Cerebras; on the routing set it routes exactly as on Groq.
