# The nightly evaluation: a measured night, and the job's size

Phase 9, step 9.1 ([ADR-0034](../decisions/0034-nightly-evaluation.md)). One night was run by hand on 11 November 2026, before the schedule started, to measure what a night costs and to size the job from it.

## Question

What does one night of the nightly evaluation cost, step by step, and how many FinanceBench dev questions can a night answer within its cap of $0.40?

## Setup

- **The night's steps,** each an evaluation script in its own process, under one ledger (`poe nightly-eval`):
  1. the copilot answers the slice's questions, end to end;
  2. the correctness judge (prompt 2);
  3. the faithfulness check (prompt 1);
  4. the LLM router decides the routing set's 138 dev questions;
  5. the data agent answers the SQL set's 28 dev questions.
- **The slice:** 40 dev questions, drawn from copilot v2's dev run in proportion to its routes and the question types (16 data, 15 doc and 9 hybrid; 13, 14 and 13 by type), with a fixed seed.
- **Models,** as in Phase 7 ([ADR-0024](../decisions/0024-second-provider.md)): gpt-oss-120b and Qwen3.8 27B on Cerebras for the strong and fast roles, gpt-oss-20b on Groq for the small one, with the judges on Cerebras's Qwen, reasoning off.
- **Fresh calls.** The run started from an empty data folder holding only the data bundle the API image is built from and FinanceBench's question files, so no earlier reply was replayed from a cache. Qdrant Cloud's production collection was read with the read-only key.
- **The cap:** $0.40, each step allowed up to a share of it counted from the start of the night (55%, 63%, 72%, 90% and 100% in this first draft). A call whose price is unknown would have counted $0.01.
- **Machine:** the laptop (`runner: local`), on the commit that became #101.

## Results

The night ran to the end without touching a step's cap: $0.3781 of $0.40.

| Step | Spent | Night so far | Minutes |
|---|---|---|---|
| Answers (40 questions) | $0.1909 | $0.1909 | 27.5 |
| Judge | $0.0268 | $0.2177 | 2.6 |
| Faithfulness | $0.0325 | $0.2502 | 1.8 |
| Routing set (138) | $0.0586 | $0.3088 | 9.1 |
| SQL set (28) | $0.0693 | $0.3781 | 4.7 |

- **By model:** $0.2059 on Cerebras's gpt-oss-120b and $0.1629 on its Qwen, so $0.369 billed by Cerebras. Groq's small role came to $0.0094 at list price, which its free tier doesn't charge.
- **An answer cost** $0.0048 on average: $0.0041 on the data route, $0.0044 on the doc route and $0.0073 on the hybrid route. The time is paced for the free tier's limits, so it measures throughput, not a visitor's wait: 35 s at the median and 91 s at the 95th percentile.

| Metric | Night | 95% interval | Questions |
|---|---|---|---|
| Correct | 0.65 | 0.50 to 0.80 | 40 |
| Answered | 0.925 | 0.80 to 0.98 (exact) | 40 |
| Faithful, doc and hybrid answers | 0.81 | 0.62 to 0.95 | 21 |
| Routing accuracy | 1.00 | 0.97 to 1.00 (exact) | 138 |
| SQL accuracy | 1.00 | 0.88 to 1.00 (exact) | 28 |

- **The same level as the last measurement.** Copilot v2 answered 0.65 of all 100 dev questions correctly on the same provider and judges ([report](copilot-v2.md)); this night answered 0.65 of 40 of them.
- **Kept:** only ids, categories and numbers, in `nightly/runs/2026-11-11-slice.json` on the `eval-history` branch, the history's first night.

## Decision: 32 questions a night

$0.378 fits the cap, but with 5.5% to spare. Fresh calls vary from night to night, and a night that reached a step's cap would be cut short and draw no verdict. So, as ADR-0034 says, the slice shrinks and the cap stays:

- **32 questions,** drawn the same way (13 data, 11 doc and 8 hybrid by route; 10 metrics, 11 domain and 11 novel questions by type), 21 of them among the measured 40. A night should cost about $0.33, about 82% of the cap.
- **The steps' shares** follow the measured costs: 50%, 57%, 65%, 82% and 100% of the cap. Each step has room above what it spent here, and a step that spends less leaves the rest to the steps after it.
- **A full run** (all 100 questions, on Sundays) should cost about $0.75 of its $1.20.
- **A month** should cost about $12, under the $15 the caps allow.

## Limits

- **One night.** The cost of a night varies with the length of the models' replies, and the first scheduled nights will show by how much. If a night is cut short, the slice shrinks again.
- **A 32-question slice detects only large drops.** With the night's four tests adjusted together, a drop is significant only when at least 8 of the 32 questions change, all the same way: 25 points. On the Sunday run's 100 questions, 8 points can show. The slice's nights show the trend and catch a breakage; the full run is the finer test.
- **The judges are models.** Their verdicts carry the caveats of [the judge guide](../concepts/llm-as-judge.md); the same judges grade every night, so the trend compares like with like.
- **The interval on faithfulness is wide,** since only the doc and hybrid answers cite pages (21 of 40).
