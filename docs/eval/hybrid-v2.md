# Hybrid answers, version 2

Phase 5, step 5.1 (the graph's hybrid node). The 13 questions of the hybrid set; no held-out split exists for it.

## Question

The Phase 4 prototype answered 10 of the hybrid set's 13 questions with every expected figure, and refused the other 3 although it had their figures, because no page it retrieved explained them ([report](hybrid-prototype.md)). Version 2 makes the changes that report set out: route each question by need, split it into a part for each agent, answer in part, and retry. Does it answer the questions the prototype refused, without losing faithfulness, and at what cost?

## Setup

- **Questions:** the [hybrid set](../data/hybrid-set.md): ten that ask about two years one filing states side by side (h01 to h10), and three that ask about five years, a middle year of which no filing in the corpus states, or states only deep in a later one (h11 to h13).
- **Version 2** (`copilot.answer.hybrid_v2`, [guide](../concepts/hybrid-answers.md#version-2)):
  - **route by need:** a question about one company and at most two consecutive years, the later with a 10-K in the corpus, goes to the doc agent alone, with its retry;
  - **split:** any other question gets a planner call (gpt-oss-120b) that writes a figures question for the data agent and a reasons question for the doc agent's retrieval;
  - **answer in part:** one answer call (gpt-oss-120b, hybrid prompt 2) that answers with what the sources support and names the rest in `missing`;
  - **retry:** when something is missing, a second search across all of the company's filings and a second answer from the larger context.
- **Compared with** the prototype (`hybrid-v1`) and the doc agent alone (`doc-agent-v4`), both from Phase 4, on the same questions.
- **Checks**, as in Phase 4: whether the answer gives every expected figure (computed from the facts database's annual values, within 1%); whether it cites the query result and a page; and faithfulness, each sentence judged against the sources it cites by Qwen3.8 27B ([ADR-0014](../decisions/0014-answer-judge.md)). Paired permutation tests ([ADR-0007](../decisions/0007-evaluation-statistics.md)).
- **Designed on these questions.** Version 2's changes come from the prototype's failures on this same set, so the set shows whether they fix what they were meant to fix, not how well they generalise. The copilot's end-to-end run on FinanceBench dev (step 5.6) sends its hybrid questions through the same code.

## Results

| | Prototype (`hybrid-v1`) | Doc agent alone (`doc-agent-v4`) | **Version 2** |
|---|---|---|---|
| Answered | 10 | 10 | **13** |
| Every expected figure | 10 | 10 | **13** |
| Every sentence supported by its citations (faithful) | 8, 0.615 (0.385 to 0.846) | 6, 0.462 (0.231 to 0.692) | 7, 0.538 (0.231 to 0.769) |
| Share of sentences supported | 0.715 (0.469 to 0.923) | 0.667 (0.442 to 0.865) | 0.833 (0.724 to 0.936) |
| Cites the query result | 9 | 0 | 3 |
| Tokens a question | 9,701 | 7,318 | 7,638 |
| Cost a question, at list prices | $0.0048 | $0.0030 | $0.0034 |
| Model time a question, median | 7.0 s | 5.0 s | 5.0 s |

- **Routing by need sent h01 to h10 to the doc agent alone,** so on those ten version 2 gives the doc agent's answers, at $0.0025 a question. h11 to h13 took the split path, at $0.0062 a question.
- **The split path answered all three five-year questions with every figure,** each figure cited to the query result. The prototype answered one of them and the doc agent none, since a middle year is in no filing the corpus holds.
- **Two answers retried:** h10 on the doc path, as the doc agent does, and h12 on the split path, whose first answer named part of the question as missing.
- **The explanations are the weak part.** h11's answer is faithful. In h12 the judge found unsupported the sentence that offers a currency benefit of 2 percent as a driver of the 2021 result, and in h13 the two sentences describing the recovery. The doc path keeps the doc agent's faithfulness on h01 to h10: 6 of 10.
- **Model time** is the time the model calls took as Groq served them; version 2's longest question took 242 s, almost all of it waiting out a spent quota.

### Computed figures

The first run's answers showed three faults in how computed figures read, none of which the checks measure:

- **Written twice:** in h11 the model wrote each year's change itself and put the calculator's placeholder after it, so each change appeared twice, the second time in raw dollars ("increased by $122 million to $1.699 billion in 2019 122,000,000"). h05 did the same with a figure in thousands. The prototype's answer to h11 had the same fault.
- **Raw dollars:** results computed from the facts database's values read "5,186,000,000".
- **Double negatives:** "fell by -1,173,000,000".

`fill`, which puts each result in place, now drops a placeholder whose result the sentence already states, writes a result of a million or more from the database's dollars in millions or billions, and shows a fall after words that say so without its minus sign ([guide](../concepts/hybrid-answers.md#version-2)). The run was then repeated from the cached model calls: four answers read differently, and every check gave the same result.

## Comparison

Paired permutation tests on the 13 questions:

| Version 2 against | Measure | Difference (95% interval) | p |
|---|---|---|---|
| Prototype | Every expected figure | +0.231 (+0.000 to +0.462) | 0.25 |
| Prototype | Faithful | -0.077 (-0.308 to +0.154) | 1.00 |
| Prototype | Share of sentences supported | +0.118 (-0.058 to +0.297) | 0.28 |
| Doc agent alone | Every expected figure | +0.231 (+0.000 to +0.462) | 0.25 |
| Doc agent alone | Faithful | +0.077 (+0.000 to +0.231) | 1.00 |
| Doc agent alone | Share of sentences supported | +0.167 (+0.000 to +0.359) | 0.25 |

Version 2 gains three questions on figures against each and loses none, but three questions all one way is a p of 0.25: 13 questions can't settle it. On faithfulness neither difference is distinguishable from chance.

## Decision

Adopt version 2 as the graph's hybrid node, as the code already does:

- it answers every question in the set with every expected figure, where both earlier systems answered 10;
- it costs 30% less than the prototype ($0.0034 against $0.0048), because the questions one filing answers skip the data agent and the planner;
- its faithfulness sits between the two earlier systems', with intervals too wide to tell them apart.

Its split path explains less faithfully than it reports figures: in two of its three answers, sentences of the explanation were judged unsupported by their pages. The validator (step 5.3) checks every cited sentence of a hybrid answer before it is shown, which is the next guard on exactly that.

## Logs

- Run: [`eval/results/hybrid/hybrid-v2/dev/`](../../eval/results/hybrid/hybrid-v2/dev/), with `items.jsonl` (per question: the path, whether it retried, the checks, tokens, model time and cost) and `summary.md`.
- Answers with their sources, the SQL and the faithfulness verdicts: `data/processed/hybrid/hybrid-v2/` (local, not committed).
- Reproduce ([runbook](../runbooks/running-evaluations.md)):

  ```bash
  uv run poe run-hybrid --agent hybrid-v2 --run hybrid-v2
  uv run poe compare-runs eval/results/hybrid/hybrid-v1/dev eval/results/hybrid/hybrid-v2/dev --metric all_figures
  ```
