# ADR-0026: Hand on what the data agent can't answer, route by the database's grain, and let a checked answer keep a labelled assessment

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** 7

## Context

The copilot's first version answered 0.49 of FinanceBench's dev questions correctly, against 0.65 for the doc agent alone on the same provider and judges ([report](../eval/copilot-dev.md)). It won where it was designed to, on the figure questions the data agent answers, and lost more elsewhere. Of 19 questions it lost to the doc agent:

- **10 went to the data agent and failed there.** 5 asked for something the facts database doesn't hold (segment sales, cash flows by activity, an effective tax rate, a one-off gain), and the data agent declined them; 2 got queries that returned no rows; 3 asked for an analyst's reading of a figure, and the data agent computed the wrong one. The graph had no path from a decline to the filings' text.
- **6 were right as drafted and wrong after the validator** ([ADR-0019](0019-validator-loop.md)). The check rejected verdicts the question asked for, because the pages state the figures but not the judgement; revisions dropped them, or refused. Two revisions also wrote computed margins as "0.33%" for 33%: the revision call sees the answer's text but not how its first calculations were scaled.
- **1 was declined as investment advice:** a question whether a company's financials were those of a high-growth company.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep version 1 | Nothing to change | 0.16 behind the doc agent alone |
| Send everything to the doc agent | Matches the doc agent alone | Gives up the data agent's lead on figure questions (32 of 33 against 29) and the query behind each figure |
| Drop the validator | Recovers the 6 validator losses | Faithfulness falls back to about 0.5 on the doc and hybrid answers |
| **Four targeted changes: a handoff, two router rules, a labelled assessment, and safer revisions** | Each addresses a recorded loss and keeps what version 1 does well | The rules were written from the dev losses, so dev measures recovery, not generalisation |

## Decision

1. **Hand a question on.** When the data agent declines, fails, or its query returns no rows, the graph sends the question to the doc agent (`after_data`), and the result and response record the handoff. A spent quota isn't handed on.
2. **Route by the database's grain** (router prompt r2, `GRAIN_RULES`). The database holds annual figures for whole companies: a question about a quarter, a segment, a product line or a region, or about a figure that isn't one of its measures, is doc (or hybrid if it asks why). A question asking for an assessment of reported figures is hybrid, and isn't investment advice.
3. **Keep a labelled assessment** (validator version 2). A sentence that begins "Assessment:" is the answer's own reading of the facts it cites. It doesn't fail the validator's check, and trimming keeps it beside at least one verified sentence, never alone. The revision prompt allows one when the question asks for a judgement and the supported facts bear it out. The evaluation's faithfulness check still grades it strictly, like any other sentence.
4. **Revise without losing the answer.** The revision prompt asks for every figure to be computed again, a percentage's expression multiplying by 100. A revision that turns an answer into a refusal is set aside: the next check cuts the answer to its verified sentences instead.

## Evidence

[The copilot's version 2: dev evaluation](../eval/copilot-v2.md):

- **Correct 0.65 (0.56 to 0.74),** against 0.49 for version 1 (+0.160, from +0.090 to +0.240; p = 0.0002) and 0.65 for the doc agent alone (+0.000, p = 1.00). Figure questions 32 of 33, against 31 and 29.
- **16 of version 1's 19 losses recovered:** 8 by router r2, 5 by the validator's changes, 4 by the handoff. One question lost against version 1.
- **Faithful 0.82 (0.71 to 0.91)** on the 55 doc and hybrid answers, against 0.49 for the doc agent alone on the same questions (+0.327, p = 0.0001).
- The validator's own cost to correctness fell from −0.06 (p = 0.03) to −0.02 (p = 0.50).
- Router r2 routes all 138 routing-set dev questions correctly, as r1 did.
- $0.0050 a question, against $0.0047.

## Consequences

- The copilot now matches the doc agent alone on correctness while answering more faithfully and showing the query behind every figure. It doesn't beat it: domain-relevant questions are still 16 against 19, two of them lost in revisions.
- An answer may now contain a sentence its sources don't state, labelled as the answer's own. The UI says so under any answer that has one; the faithfulness metric keeps counting it.
- The routing rules were written from dev losses. The FinanceBench test split, opened once when the copilot is final, will say how far they generalise. The classifier router trained on r1's labels ([ADR-0025](0025-classifier-router.md)) should be relabelled with r2 before it is used with this version.
- Version 1 can be reproduced from commit `789f825`.

## References

- [ADR-0017](0017-routing.md), routing; [ADR-0018](0018-graph-design.md), the graph; [ADR-0019](0019-validator-loop.md), the validator loop.
- Madaan et al., [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651), 2023, on revision loops that can make answers worse as well as better.
