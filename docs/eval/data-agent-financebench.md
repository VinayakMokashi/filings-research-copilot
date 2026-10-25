# Data agent: FinanceBench's metrics questions

Phase 4, step 4.5. FinanceBench dev split only; the held-out test split was not opened.

## Question

FinanceBench's metrics questions ask for figures from the financial statements: a capital expenditure, a ratio, a three-year average. Does the data agent, which answers them with SQL over the XBRL facts database, get them right more often than the doc agent, which reads them off filing pages? What does an answer cost, and where does it go wrong?

## Setup

- **Questions:** the 33 metrics-generated dev questions, on 15 companies: single figures, ratios, year-over-year changes, three-year averages, days payable outstanding and the cash conversion cycle. FinanceBench's analysts wrote them, so unlike the SQL set they test the agent on wording it wasn't shaped on.
- **Data agent** (`data-agent-v1`), exactly as it ran on the SQL set: every table offered, value linking, table selection on `groq/qwen/qwen3.8-27b`, SQL on `groq/openai/gpt-oss-120b` ([guide](../concepts/text-to-sql-agent.md)). Nothing was changed for this run. The written answer comes from gpt-oss-120b, the doc agent's answer model, so the two agents differ only in where their numbers come from.
- **Doc agent** (`doc-agent-v4-full`), the Phase 3 agent, on the same 33 questions ([report](doc-agent-dev.md)).
- **Correctness:** the doc agent's two judges, Qwen with rubric v2 (`qwen3.8-27b-p2`) and gpt-oss-20b with the same rubric ([ADR-0014](../decisions/0014-answer-judge.md)). They were checked against reference labels from a Claude model, not a person.
- **The ceiling.** In Phase 1 all 33 questions were written by hand as formulas over `annual_values`, and all 33 matched the reference answers ([cross-check](../../eval/results/facts/financebench-dev-checks.md)); one tag, Nike's for inventory, was added to the facts rules along the way. So every figure is in the database, and this run tests the step from the question's wording to the right query.
- **Intervals:** 95% bootstrap intervals, plus exact binomial intervals because the shares are near 1; a paired permutation test between the agents ([ADR-0007](../decisions/0007-evaluation-statistics.md)).

## Results

### Correctness

| Agent | Qwen judge (95% interval) | Exact 95% interval | gpt-oss-20b judge |
|---|---|---|---|
| **Data agent** | **32 of 33: 0.97 (0.91 to 1.00)** | 0.84 to 1.00 | 32 of 33 |
| Doc agent | 29 of 33: 0.88 (0.76 to 0.97) | 0.72 to 0.97 | 29 of 33 |

The two judges agree on every verdict for both agents. The data agent answered all 33 questions, declined none and failed none.

### How it got there

- Every query used `annual_values` and `companies` alone, as the Phase 1 formulas do.
- One query needed a repair: General Mills's cash conversion cycle, the longest formula in the set.
- Where a question defines its measure (return on assets as one year's net income over the average of two years' total assets, say), the query follows the question, not the simpler definition in the hints.
- Rounding happens in SQL, at the precision the question asks for, so the written answer quotes the figure rather than computing it.

### Cost and speed

On the same 33 questions:

| Agent | Tokens a question | Model time, p50 / p95 | Cost a question at list prices |
|---|---|---|---|
| Data agent | 4,868 (4,005 in, 863 out) | 2.78 s / 4.09 s | $0.0025 |
| Doc agent | 5,156 (4,568 in, 588 out) | 2.13 s / 5.52 s | $0.0010 |

The data agent uses fewer tokens but costs more. Its table-selection call, about 1,900 tokens, runs on Qwen3.8 27B, which lists at about five times gpt-oss-120b's price for input and seven times for output. That one call is two thirds of the cost. On gpt-oss-120b it would cost about $0.0003, bringing the total to about $0.0011, the doc agent's level; whether the selections stay as good is untested. The data agent needs no vector index or embedding model, only the SQLite file. Its three calls (selection, SQL, answer) run one after another. Both agents had rare slow calls from the provider: the data agent's slowest answer took 33 seconds of model time, the doc agent's 57.

## Comparison

| | Data agent right | Data agent wrong |
|---|---|---|
| **Doc agent right** | 29 | 0 |
| **Doc agent wrong** | 3 | 1 |

The data agent is right on every question the doc agent gets. Correct share +0.09 (0.00 to +0.21), p = 0.25 (paired permutation test), with either judge: with three questions between them, 33 questions can't show the difference is real.

Where the two differ:

- **Two calculations across years, which the doc agent refused.** Activision Blizzard's capex relative to revenue, averaged over three years, needs six figures, and Walmart's days payable outstanding needs two years of payables and inventory and a year of cost of sales. After its retry the doc agent still lacked some of them and said so: a year of revenue for Activision, most of Walmart's. The data agent's queries read every figure from `annual_values` and did the arithmetic in SQL.
- **One question of precision.** For Coca-Cola's return on assets the doc agent answered 1.46%, which is the reference's 0.01 at the two decimals the question asks for, written as a percentage. The judge marked it wrong; the Phase 3 review counted it as arguably correct. The data agent's query rounded as asked.
- **The question both miss.** American Water Works's dividends paid in fiscal 2020, in USD billions. The doc agent gave a wrong figure, $0.327 billion. The data agent returned the reported $389 million as $0.39 billion; the reference says $0.40, the same figure rounded to one decimal and written with two. The figure is right, but at the two decimals the reference shows it doesn't match, and both judges hold the answer to that.

## Error analysis

The data agent's one answer that wasn't correct, read against the reference, its SQL and its rows ([review](../../eval/results/errors/data-agent-v1--qwen3.8-27b-p2/dev/review.json)):

| Reason | Answers |
|---|---|
| The reference rounds more coarsely than it shows | 1 |

No query picked a wrong metric, year, company or formula. The doc agent's four misses on these questions were two refusals on calculations across years, one misread figure and one rounding case ([doc agent report](doc-agent-dev.md)).

## Decision

- **Figure questions go to the data agent.** On FinanceBench's metrics questions it is right wherever the doc agent is, and it also answers calculations across years that the doc agent can't assemble. In Phase 5 the router sends such questions to the data agent. If it sent all 33 there and everything else to the doc agent, the copilot would answer 68 of the 100 dev questions correctly instead of 65, the most routing these questions could add.
- **No change to the data agent.** It needs nothing for these questions that the SQL set didn't already bring out.
- **Two levers, both untested:** the table-selection call on gpt-oss-120b would cut the cost by more than half. The judge's precision rule (equal at the reference's precision, an open item from Phase 3) would settle the rounding cases on both sides.
- **The fair test is still ahead.** The facts database was checked against these 33 questions in Phase 1, and the hints were tuned on the SQL set's dev split. The held-out FinanceBench test split checks both agents on questions neither was fitted to.

## Logs

| What | Where |
|---|---|
| The run: answered, declined, failed, repaired, tokens, latency, cost | [`eval/results/answers/data-agent-v1/dev/`](../../eval/results/answers/data-agent-v1/dev/summary.md) |
| Correctness by judge | [Qwen](../../eval/results/correctness/data-agent-v1--qwen3.8-27b-p2/dev/summary.md), [gpt-oss-20b](../../eval/results/correctness/data-agent-v1--gpt-oss-20b-p2/dev/summary.md) |
| The review of the answer that wasn't correct | [`review.json`](../../eval/results/errors/data-agent-v1--qwen3.8-27b-p2/dev/review.json) |

To reproduce the numbers:

```bash
uv run poe answer-with-data                    # needs the facts database and GROQ_API_KEY
uv run poe judge-answers --run data-agent-v1
FRC_LLM_FAST_MODEL=groq/openai/gpt-oss-20b uv run poe judge-answers --run data-agent-v1
R=eval/results/correctness
uv run poe compare-runs $R/doc-agent-v4-full--qwen3.8-27b-p2/dev $R/data-agent-v1--qwen3.8-27b-p2/dev \
  --metric correct --where question_type=metrics-generated
```

The answers, SQL, rows and verdicts hold FinanceBench's figures and the models' answers, so they stay in the local `data/processed/` folder; the committed files hold ids and numbers only.
