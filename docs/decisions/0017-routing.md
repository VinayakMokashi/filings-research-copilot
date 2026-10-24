# ADR-0017: Route with an LLM on the strong model, and keep a semantic router as its fallback

- **Status:** Accepted
- **Date:** 2026-10-24
- **Phase:** 5

## Context

Every question passes through the router before anything else, so its accuracy caps the copilot's, and its latency and cost are paid on every question, small talk included. It chooses among six routes: the doc agent, the data agent, the hybrid of the two, a research brief, small talk and a polite decline ([guide](../concepts/semantic-routing.md)).

Three constraints shape the choice:

- **Measured on the routing set.** Its dev side has 138 questions from 46 seeds, each with two paraphrases ([data card](../data/routing-set.md)). The floors are the keyword rules (0.623) and the majority route (0.217).
- **The free tier.** Groq's daily token caps are per model, and the answer models already spend most of theirs.
- **Phase 7.** The plan trains a small classifier with an LLM router as its teacher, so the LLM router's labels need to be good.

## Options considered

All on routing dev, 138 questions ([report](../eval/routing.md)):

| Router | Accuracy (95% interval) | Latency, median | Cost a question | For | Against |
|---|---|---|---|---|---|
| Keyword rules | 0.623 (0.543 to 0.703) | under 1 ms | none | Free and instant | Written on the seeds: 0.957 there, 0.457 on paraphrases |
| Semantic, a vote of the five nearest examples | 0.391 (0.312 to 0.471) | 8 ms | none | Free, fast, no prompt to maintain | Its neighbours share the topic, not the route |
| Semantic, companies and years masked, nearest centroid | 0.739 (0.667 to 0.812) | 8 ms | none | Free, fast, and robust to wording | Confuses `decline` with small talk and `hybrid` with `data`; chosen on dev |
| LLM, gpt-oss-20b (the `small` role) | 0.964 (0.928 to 0.993) | 0.68 s | $0.00010 | Cheapest LLM; its own quota | Misrouted "Which companies do you cover?" to the doc agent and two poems to briefs |
| **LLM, gpt-oss-120b (the `strong` role)** | **1.000 (exact 0.974 to 1.000)** | **0.51 s** | **$0.00019** | Every dev question right; fast on Groq | Uses the answer model's daily quota |
| LLM, Qwen3.8 27B (the `fast` role) | 1.000 (exact 0.974 to 1.000) | 0.33 s | $0.00080 | Fastest | Four times the cost of gpt-oss-120b |
| A cascade: semantic first, the LLM when unsure | See the report | | | Fewer LLM calls | Every call it saves risks a route the LLM would have got right |

## Decision

1. **The LLM router decides, on the `strong` role** (gpt-oss-120b), with prompt `r1`: the six route definitions, the routing set's labelling rules, the 28 measures the facts database holds, and 13 examples written for the prompt.
2. **The semantic router runs beside it** (companies and years masked, nearest route centroid, over the dev questions). It costs 8 ms and no tokens, its route is recorded in every trace as a second opinion, and it decides when the LLM call fails or its reply can't be read. In the copilot this is `CascadeRouter(semantic, llm, threshold=math.inf)`.
3. **No semantic-first cascade.** Letting the semantic router decide when its centroid margin is at least 0.08 would skip 9% of the router calls with no error on dev; at 0.05 it would skip 17% and misroute one question. Either saves at most $0.00003 a question, and both thresholds were found on the same dev questions, so the saving isn't worth a misroute the LLM wouldn't make.
4. **The `small` role stays**, for the copilot's cheapest calls: small-talk replies now, and the validator's checks (step 5.3). It was added for routing, before the full runs showed that gpt-oss-20b misroutes questions about the assistant and out-of-scope requests.
5. **Frozen until the milestone.** Prompt `r1` and the semantic router's configuration don't change on dev; the routing set's held-out test split is opened once, at Phase 5's milestone.

## Evidence

- **Accuracy.** gpt-oss-120b routed all 138 dev questions correctly; gpt-oss-20b routed 133. All five questions they disagree on favour gpt-oss-120b, which is a sign test p of 0.06, so not significant on dev, and the five come from three seeds. The choice rests on cost as much as on the count. The extra $0.00009 a question buys back all five misroutes, and four of them are among the first things a demo shows: "Which companies do you cover?" and its paraphrase sent to the doc agent, and two requests for a poem sent to the brief writers. The fifth, a terse overview request routed to `hybrid`, would still have got a fair answer.
- **The fallback.** On the day of the evaluation the strong model's quota ran out, and the copilot's router fell back to its semantic half live: "Hi! Which companies do you cover?" went to small talk, and a hybrid-set question to `hybrid` ([ADR-0018](0018-graph-design.md) has the run).
- **The test split,** opened once at Phase 5's milestone with both routers frozen: gpt-oss-120b routed all 60 questions correctly (exact 0.940 to 1.000), and the masked-centroid fallback 0.800 (0.700 to 0.900), against 0.650 for the keyword rules ([report](../eval/routing.md#the-test-split)).
- **Against the floors.** On paraphrases, where the keyword rules weren't written, the masked-centroid router beats them by +0.283 (+0.152 to +0.413), p = 0.0001. Every LLM router beats the keyword rules by +0.34 to +0.38 on all of dev (Holm-adjusted p = 0.0004).

## Consequences

- **Every question pays one strong-model call** before a specialist starts: about 970 tokens, 0.5 s at the median and $0.0002 at list prices. On the free tier those tokens come out of the answer model's daily cap, which lengthens evaluation runs by about a fifth.
- **During an outage** the copilot keeps routing at the semantic router's accuracy: 0.74 on dev and 0.80 on test. Its confusions send `hybrid` questions to one agent instead of both, which can cost the answer its figures or its explanation, and `decline` requests elsewhere: to small talk on dev, and on test to the data agent (share-price predictions, requests for non-public information) or to the brief writers. In an outage, those requests rely on the agent that receives them declining what it can't answer.
- **The labels and the prompt share their rules.** The prompt carries the routing set's labelling rules, so the LLM router is graded against labels made by the rules it was given, and its examples were written after reading dev. The test split, with seeds the prompt never saw, is the fair check.
- **Phase 7** trains a small classifier on the LLM router's labels; it replaces the LLM call only if it matches it on the test split.

## References

- The [routing report](../eval/routing.md), with every run, the confusion matrices and the paired tests.
- The [semantic routing guide](../concepts/semantic-routing.md).
- Aurelio AI, [Semantic Router](https://github.com/aurelio-labs/semantic-router), for the utterance-matching design the semantic router follows.
