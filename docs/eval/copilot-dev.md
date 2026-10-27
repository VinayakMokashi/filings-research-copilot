# The copilot end to end: dev evaluation

Phase 5, step 5.6. FinanceBench dev, 100 questions; the held-out test split was not opened.

## Question

Phase 3 measured the doc agent alone, and Phase 4 the data agent alone. Does the whole copilot, which routes each question to the doc, data or hybrid agent, checks what they write and revises it, answer FinanceBench's dev questions better than the doc agent alone? And what does that cost in steps, money and time?

## Setup

- **Questions:** the 100 dev questions (20 companies): 34 domain-relevant, 33 metrics-generated and 33 novel-generated. Each goes through the graph as the first question of a thread of its own, so no notes or history carry over ([ADR-0018](../decisions/0018-graph-design.md)).
- **The copilot:** `poe run-copilot` in batch mode. The nodes run in order: rewrite, understand, route (the LLM router, [ADR-0017](../decisions/0017-routing.md)), then the doc, data or hybrid agent ([hybrid answers, version 2](hybrid-v2.md)), synthesise, validate and revise ([ADR-0019](../decisions/0019-validator-loop.md)), respond. A spent quota stops the run so it can resume, rather than answering "try again later".
- **Models:**
  - gpt-oss-120b (`strong`) and Qwen3.8 27B (`fast`) on Cerebras, with Qwen's reasoning off as on Groq, where every earlier result was measured ([ADR-0024](../decisions/0024-second-provider.md));
  - gpt-oss-20b (`small`), the validator's checker, on Groq.
- **Baselines:**
  - the doc agent alone, with the Phase 3 configuration, answered again on Cerebras (`doc-agent-v4-cerebras`), so the comparison holds the provider fixed;
  - the Phase 3 answers on Groq (`doc-agent-v4-full`), for the provider's own effect.
- **Before the validator:** each answer as the specialist first wrote it is kept as a run of its own (`copilot-v1-drafts`), so judging both measures what the validator changed inside the copilot.
- **Graded** by the Phase 3 judges on Cerebras: correctness (Qwen3.8 27B, rubric prompt 2, figures compared by code) and faithfulness (prompt 1). On the doc agent's dev answers they agree with the same judges on Groq on 99 of 100 verdicts and 91 of 94 ([ADR-0024](../decisions/0024-second-provider.md)).
- **Agent metrics** (from the run's own records): the route, the nodes each question ran, whether the specialist answered or declined on purpose (tool success), the validator's revisions, and the tokens, cost and time of each question. Latency by node comes from the run's trace file (`poe latency-report`).
- **Tests:** paired permutation tests ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

### Correctness

| Outcome | Copilot | Copilot before the validator | Doc agent alone, on Cerebras | Doc agent alone, Phase 3 answers |
|---|---|---|---|---|
| Correct | 0.49 (0.39 to 0.59) | 0.55 (0.45 to 0.65) | 0.65 (0.55 to 0.74) | 0.64 (0.55 to 0.73) |
| Incorrect | 0.33 | 0.31 | 0.28 | 0.30 |
| Refused or declined | 0.18 | 0.14 | 0.07 | 0.06 |

| Question type | Copilot | Doc agent alone, on Cerebras | Doc agent alone, Phase 3 answers |
|---|---|---|---|
| Metrics-generated (33) | 31 | 29 | 29 |
| Domain-relevant (34) | 8 | 19 | 19 |
| Novel-generated (33) | 10 | 17 | 16 |

**The copilot answers fewer questions correctly than the doc agent alone.** It gains where it was designed to: the data agent answers 31 of the 33 figure questions. It loses more on the questions that ask an analyst's reading of the filings. Against the doc agent alone on the same provider, it loses 19 questions and gains 3:

| Why the copilot lost a question the doc agent answered | Questions |
|---|---|
| An analyst's question sent to the data agent, which declined it (5) or answered it wrongly (5) | 10 |
| The validator: the draft was right, and its revision or trimmed answer wasn't | 6 |
| The hybrid route's draft was already wrong | 1 |
| The data route's draft was already wrong, on a figure question | 1 |
| Sent to the decline route | 1 |

The 3 gains are figure questions the data agent answered. Against the doc agent's Phase 3 answers the picture is the same: 20 lost, among them 8 analyst questions on the data route and the same 6 to the validator, and 5 gained. The validator fixed no question. It changed 8 verdicts: 6 right answers became wrong (4) or refusals (2), and 2 wrong answers became refusals.

### Faithfulness

The faithfulness check reads each sentence against the filing pages it cites. The data agent's answers cite the facts database as a whole, not numbered pages, so the check counts every sentence they write as unsupported. Their figures come from the query's rows, and the correctness judge compares them with the reference. So faithfulness is reported for the 42 doc and hybrid answers:

| | Copilot | Before the validator | Doc agent alone, on Cerebras | Doc agent's Phase 3 answers |
|---|---|---|---|---|
| Faithful: every sentence supported | 0.76 | 0.48 | 0.43 | 0.48 |
| Share of sentences supported | 0.83 | 0.71 | 0.69 | 0.68 |

Over all 82 answers, including the data agent's, the copilot scores 0.39 faithful (0.28 to 0.50); the run's results keep both readings.

### Where the questions went

| Question type | Data | Doc | Hybrid | Decline |
|---|---|---|---|---|
| Metrics-generated (33) | 33 | 0 | 0 | 0 |
| Domain-relevant (34) | 4 | 12 | 17 | 1 |
| Novel-generated (33) | 10 | 19 | 3 | 1 |
| **All (100)** | **47** | **31** | **20** | **2** |

- **Every figure question went to the data agent**, as routing by need intends. The LLM router decided every question; its semantic fallback was never used.
- **The hybrid route's agent took the doc path for 17 of its 20 questions**, because one filing held both the figures and the explanation. It split only 3 between the data and doc agents ([hybrid answers, version 2](hybrid-v2.md)).
- **Two questions were declined.** Both have reference answers. One asks an analyst's judgement about a company's growth, which the router read as investment advice. The other asks what shareholders would receive in a hypothetical bankruptcy, which it read as speculation.

### What the copilot did

From the run's own records, for all 100 questions:

| Measure | All | Data | Doc | Hybrid |
|---|---|---|---|---|
| Answered (rather than declined or refused) | 0.82 (0.74 to 0.89) | 0.85 | 0.77 | 0.90 |
| Tool success | 1.00 | 1.00 | 1.00 | 1.00 |
| Revised by the validator | 0.26 (0.18 to 0.35) | 0 | 0.39 | 0.70 |
| Steps (nodes run) | 8.7 | 8.0 | 9.0 | 10.1 |
| Cost a question, at list prices | $0.0047 | $0.0036 | $0.0049 | $0.0076 |
| Tokens a question | 10,184 | 5,536 | 12,251 | 18,807 |

- **Tool success** counts a specialist that answered or declined on purpose; none failed.
- **The data agent declined 7 of its 47 questions.** All 7 were domain-relevant or novel-generated questions about something the facts database doesn't hold: segments, product lines, an effective tax rate, investing cash flows. The copilot doesn't yet pass such a question on to the doc agent.
- **The validator checked 46 answers** from the doc and hybrid routes: 20 passed first, 15 were revised once and 11 twice. 35 of the 46 ended faithful by its check.
- **Tokens by model:** 730,191 on gpt-oss-120b, 133,876 on Qwen3.8 27B and 154,307 on gpt-oss-20b. The whole run cost $0.47.

### Time

| Route | Runs | Median | 95th percentile |
|---|---|---|---|
| Data | 47 | 17.8 s | 20.3 s |
| Doc | 31 | 40.2 s | 67.9 s |
| Hybrid | 20 | 52.8 s | 116.2 s |
| Decline | 2 | 3.7 s | 3.7 s |

These are batch times: the run pauses at least 3 seconds after every model call and paces tokens to stay inside the providers' limits. The routing node shows the effect most plainly: a median of 3.5 seconds for a call that takes about half a second. The copilot run through the API makes no such pauses. The node with the longest tail is the validator's: its 95th percentile is 20 seconds, the time a check takes on Groq's free tier.

## Comparison

Paired permutation tests on correctness, with every run graded by the same judges:

| Comparison | Questions | Difference (95% interval) | p |
|---|---|---|---|
| Copilot against the doc agent alone, on Cerebras | 100 | -0.160 (-0.250 to -0.080) | 0.0003 |
| — domain-relevant | 34 | -0.324 (-0.500 to -0.176) | 0.0005 |
| — metrics-generated | 33 | +0.061 (-0.061 to +0.182) | 0.62 |
| — novel-generated | 33 | -0.212 (-0.364 to -0.091) | 0.016 |
| Copilot against the doc agent's Phase 3 answers | 100 | -0.150 (-0.250 to -0.060) | 0.004 |
| Copilot against its own drafts (the validator) | 100 | -0.060 (-0.110 to -0.020) | 0.033 |
| Drafts against the doc agent's Phase 3 answers (routing and the specialists) | 100 | -0.090 (-0.170 to -0.010) | 0.064 |
| The doc agent on Cerebras against its Phase 3 answers (the provider) | 100 | +0.010 (-0.050 to +0.070) | 1.00 |

The provider makes no difference to the doc agent's answers, so the copilot's loss is its own. On the 42 doc and hybrid answers, faithfulness rises from the drafts' 0.48 to 0.76 (+0.286, from +0.167 to +0.429; p = 0.0003), and from the doc agent's 0.43 on the same questions on Cerebras (+0.333, from +0.190 to +0.476; p = 0.0001).

## What Phase 5 shows

Phase 5's exit criterion is met: the end-to-end dev results are in, and every node of every run is in the trace file. The results make three changes the next to try, each measurable against this run as a copilot version 2:

- **Hand a declined question on.** When the data agent finds nothing in the facts database to answer with, the copilot should ask the doc agent instead of declining. The data agent declined 5 of the 10 questions lost on the data route, and the doc agent alone had answered all 5 correctly.
- **Keep analyst questions off the data route.** A question about a segment, a product line or a ratio the database doesn't hold reads like a figures question, and the router sends it to the data agent, which can only decline it or compute the wrong figure. The router's rules and examples are where to fix this, measured on the routing set as well as here.
- **Let an answer keep a labelled judgement.** The validator removes judgements the cited sources don't state, which keeps answers faithful but costs the analyst questions their verdict, as its own evaluation found ([ADR-0019](../decisions/0019-validator-loop.md)). An answer could keep such a judgement as its own, labelled apart from the cited facts.

The figure questions show what routing by need is for: the data agent answered 31 of 33 correctly, and a question on the data route cost $0.0036 and took 18 seconds at the median in this batch run.

**Limits:** one run of each system on the 100 dev questions, so a few questions move each comparison; the judges are models, checked against reference labels from a stronger model, not a person ([ADR-0014](../decisions/0014-answer-judge.md)); the drafts are the specialists' first answers inside the same run, not an independent system; times include batch pauses. The held-out test split stays closed until the copilot is final.

## Logs

- Runs (question ids, verdicts and metrics only): [`eval/results/copilot/copilot-v1/dev/`](../../eval/results/copilot/copilot-v1/dev/) for the agent metrics; [`eval/results/correctness/`](../../eval/results/correctness/) and [`eval/results/faithfulness/`](../../eval/results/faithfulness/) for `copilot-v1`, `copilot-v1-drafts` and `doc-agent-v4-cerebras`, judged by `qwen-3.8-27b`; [`eval/results/latency/copilot-v1.json`](../../eval/results/latency/copilot-v1.json) for the times by route and node.
- The answers, drafts and traces: `data/processed/answers/copilot-v1/`, `copilot-v1-drafts/`, `doc-agent-v4-cerebras/` and `data/traces/copilot-v1.jsonl` (local: FinanceBench's licence keeps answers to its questions out of the repository).
- Reproduce ([runbook](../runbooks/running-evaluations.md)), with `FRC_LLM_STRONG_MODEL=cerebras/gpt-oss-120b` and `FRC_LLM_FAST_MODEL=cerebras/qwen-3.8-27b` set:

  ```bash
  uv run poe run-copilot --run copilot-v1
  uv run poe judge-answers --run copilot-v1
  uv run poe check-faithfulness --run copilot-v1
  uv run poe judge-answers --run copilot-v1-drafts
  uv run poe check-faithfulness --run copilot-v1-drafts
  uv run poe answer-questions --run doc-agent-v4-cerebras
  uv run poe judge-answers --run doc-agent-v4-cerebras
  uv run poe latency-report data/traces/copilot-v1.jsonl
  uv run poe compare-runs eval/results/correctness/doc-agent-v4-cerebras--qwen-3.8-27b-p2/dev eval/results/correctness/copilot-v1--qwen-3.8-27b-p2/dev --metric correct
  ```
