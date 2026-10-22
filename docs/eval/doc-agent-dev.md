# Doc agent: dev evaluation

Phase 3, step 3.7. FinanceBench dev split only; the held-out test split was not opened.

## Question

How often does the doc agent answer FinanceBench's questions correctly from filing text alone, how well do its citations hold up, what does an answer cost, and where do the wrong answers come from?

## Setup

- **Questions:** the 100 dev questions (20 companies): 34 domain-relevant, 33 metrics-generated, 33 novel-generated.
- **Agent:** filings resolved from the question, three rewrites and fused dense search over page chunks ([ADR-0012](../decisions/0012-query-understanding-and-rewriting.md)); numbered sources within 3,000 tokens, one JSON answer call with citations and calculations, and one retry aimed at what a refusal names as missing ([ADR-0013](../decisions/0013-answer-format.md)). Answer model `groq/openai/gpt-oss-120b`, rewrites `groq/qwen/qwen3.8-27b`, both at temperature 0.
- **Two versions.** `doc-agent-v3-full` is the agent as built in steps 3.3 to 3.5. `doc-agent-v4-full` changes only what happens after the model replies: calculations may use earlier results, and placeholders may scale a result or give its decimals (`{c1*100:.1f}`). The model's replies are identical, so v4 was rebuilt from the model-call cache with no new calls.
- **Correctness:** the Qwen judge with rubric v2 (`qwen3.8-27b-p2`), and gpt-oss-20b with the same rubric as a second judge ([ADR-0014](../decisions/0014-answer-judge.md)). Both were checked against 41 reference labels from a Claude model, **not a person**: Qwen agrees on all 41, gpt-oss-20b on 38 (kappa 0.84). Read every correctness number with that caveat.
- **Faithfulness:** whether each sentence is supported by the sources it cites, judged by the same two models with one call per answer ([faithfulness](../../src/copilot/eval/faithfulness.py)); not checked against any labels.
- **Intervals:** 95% bootstrap intervals over questions; paired permutation tests between versions ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

The numbers are for v4; v3 differs only where the comparison below says so.

### Correctness

| Outcome | Qwen judge (95% interval) | gpt-oss-20b judge |
|---|---|---|
| **Correct** | **0.65 (0.56 to 0.74)** | 0.63 (0.54 to 0.72) |
| Incorrect | 0.29 (0.20 to 0.38) | 0.31 (0.22 to 0.40) |
| Refused | 0.06 (0.02 to 0.11) | 0.06 (0.02 to 0.11) |

By question type, with the Qwen judge:

| Question type | Questions | Correct (95% interval) | Incorrect | Refused |
|---|---|---|---|---|
| Metrics-generated | 33 | 0.88 (0.76 to 0.97) | 2 | 2 |
| Domain-relevant | 34 | 0.59 (0.41 to 0.74) | 12 | 2 |
| Novel-generated | 33 | 0.48 (0.30 to 0.67) | 15 | 2 |

Questions that ask for a figure from the statements are answered well; questions that ask for a judgement or a narrative fact are not. For scale, FinanceBench's authors report that GPT-4-Turbo with a retrieval system answered 81% of their 150 questions incorrectly or refused, graded by people; their setup and grading differ from these, so that is context, not a comparison.

### Evidence and citations

| Measure | Value (95% interval) |
|---|---|
| An evidence page among the sources | 0.73 (0.64 to 0.82) |
| An evidence page among the cited sources | 0.64 (0.55 to 0.74) |
| Answers without a valid citation | 0.03 (0.00 to 0.07) |
| Faithful: every sentence supported by its citations (Qwen / gpt-oss-20b) | 0.63 (0.53 to 0.72) / 0.68 (0.59 to 0.78) |
| Sentences supported (Qwen / gpt-oss-20b) | 0.77 / 0.79 |
| Citation precision: citations that contribute to their sentence (Qwen / gpt-oss-20b) | 0.93 / 0.84 |

Faithfulness also splits by question type (Qwen): 0.87 of metrics-generated answers are faithful, 0.61 of novel-generated and 0.41 of domain-relevant ones, whose judgement sentences often go beyond what their cited pages say. A figure the model computed itself instead of through the calculator counts as unsupported, even when its inputs are on the cited page, because the faithfulness judge doesn't do arithmetic.

Correctness follows the evidence. With an evidence page in the context, 53 of 73 answers are correct (0.73); without one, 12 of 27 (0.44), since other pages can state the same figures. Faithful answers are correct for 48 of 59; unfaithful ones for 17 of 35.

### Refusals and the retry

16 questions began with a refusal and were retried with a search for what the refusal named as missing. After the retry, 6 were answered correctly, 4 incorrectly, and 6 were refused again. Of the 6 final refusals, 2 had an evidence page in their context.

### Latency and cost

- **Model time:** 2.34 seconds per question at the median and 5.52 at the 95th percentile, the answer call plus the retry where there was one. The rewrites came from the cache in these runs; live, they add about 1.4 seconds at the median, requested in parallel (ADR-0012).
- **Tokens:** 5,403 per question on average, with a retried question about twice a first answer.
- **Cost:** about $0.0011 per question at Groq's list prices, $0.11 for the run. On the free tier it cost nothing, but the strong model's rolling daily cap of 200,000 tokens made the run take three days.

## Comparison

| Measure | v3 | v4 |
|---|---|---|
| Correct, Qwen judge | 0.65 | 0.65 (difference +0.00, p = 1.0) |
| Correct, gpt-oss-20b judge | 0.64 | 0.63 (difference −0.01, p = 1.0) |
| Failed calculations | 11 | 0 |
| Answers showing an unfilled placeholder | 3 | 0 |
| Answer texts changed | | 3 |

The fix changed what reaches the reader, not what the judges decide. Two of the three changed answers were wrong for other reasons and stayed wrong. The third, a gross margin of 4.9% against the reference's 4.8%, stayed correct for the Qwen judge and became incorrect for the stricter gpt-oss-20b once its figures were filled in, a borderline case under the 1% rule.

## Error analysis

Every answer that wasn't correct, sorted by the first rule that applies ([`copilot.eval.errors`](../../src/copilot/eval/errors.py)), Qwen judge, v4:

| Category | Domain-relevant | Metrics-generated | Novel-generated | All |
|---|---|---|---|---|
| Refused, evidence retrieved | 1 | 1 | 0 | 2 |
| Refused, evidence not retrieved | 1 | 1 | 2 | 4 |
| Calculation broke | 0 | 0 | 0 | 0 (4 in v3) |
| Evidence not retrieved | 5 | 0 | 6 | 11 |
| Wrong with the evidence in context | 7 | 2 | 9 | 18 |

Reading each of the 29 incorrect answers against its reference and sources ([review](../../eval/results/errors/doc-agent-v3-full--qwen3.8-27b-p2/dev/review.json)) gives the reasons behind both "wrong" rows:

| Reason | Answers | What it looks like |
|---|---|---|
| A different definition of the measure | 6 | A quick ratio of cash and receivables over current liabilities, where the reference subtracts inventories from current assets |
| Incomplete, or a different selection of facts | 6 | Restructuring liabilities described without the share that is employee-related, which is the reference's whole answer |
| Misread or misreasoned | 6 | "Lost the least cash" read as the smallest outflow, when operating activities brought cash in |
| Wrong line item or scope | 4 | Adjusted EBIT reported as adjusted EBITDA; domestic stores counted instead of all stores |
| Wrong period | 3 | A dividend record "as of 2019" from the 2018 10-K, where the reference uses the 2022 one |
| A judgement that differs from the reference | 2 | Whether a new chief executive's previous company counts as similar |
| Arguably correct: the judge may be too strict | 2 | A return on assets of 1.46%, which rounds to the reference's 0.01; a tax rate whose sign follows another convention (the reference labels side with the judge on this one) |

Retrieval is the smaller problem. In 18 of the 29 wrong answers the evidence page was in the context, and the model read it differently from the analyst who wrote the reference. Definitions, completeness and the choice of filing account for more errors than finding the page.

## Decision

- **v4 is the Phase 3 doc agent.** It answers 65% of dev questions correctly by the Qwen judge (0.56 to 0.74) and 88% of the figure questions, cites an evidence page for 64% of questions, and costs about a tenth of a cent per question.
- **Next levers, in order of the errors they would address:**
  1. Definitions: ratio and margin questions name a measure the filing doesn't print. The facts database's metric definitions (Phase 1) can be given to the answer model, or such questions routed to the data agent (Phases 4 and 5).
  2. Completeness and period: the four-sentence limit may cut lists short, and "as of" questions should prefer the latest filing; both are changes to the prompt and to query understanding.
  3. The judge's precision rule: the computed comparisons should also say whether two figures are equal at the reference's precision, the case behind one of the two answers it got wrong.
- **Still open:** a person check of the judge (about 20 answers), and the held-out test split, which stays closed until the milestone evaluation.

## Logs

| What | Where |
|---|---|
| Answers, structural measures | [`eval/results/answers/doc-agent-v4-full/dev/`](../../eval/results/answers/doc-agent-v4-full/dev/summary.md), and [v3](../../eval/results/answers/doc-agent-v3-full/dev/summary.md) |
| Correctness by judge | [`eval/results/correctness/`](../../eval/results/correctness/) |
| Faithfulness by judge | [`eval/results/faithfulness/`](../../eval/results/faithfulness/) |
| Error categories, cost and latency | [`eval/results/errors/`](../../eval/results/errors/) |
| Judge agreement with the reference labels | [`eval/results/judge-agreement/`](../../eval/results/judge-agreement/) |

The answers, sources, verdicts and reasons behind these files hold FinanceBench text and model answers, so they stay in the local `data/processed/` folder; the committed files hold ids and numbers only.
