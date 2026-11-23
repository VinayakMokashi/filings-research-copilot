# The nightly evaluation: a measured night, the job's size, the first nights and the first baseline

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

## The first nights

The schedule started on 12 November. Every night ran on Cerebras, with Groq's gpt-oss-20b for the small role; a night's date is in IST.

| Night | Set | Started (UTC) | Spent | Correct | Answered | Faithful | Routing | SQL |
|---|---|---|---|---|---|---|---|---|
| 11 Nov, by hand | 40 questions | 00:53 | $0.378 | 0.65 (40) | 0.93 (40) | 0.81 (21) | 1.00 | 1.00 |
| 12 Nov | Slice | 01:57 | $0.348 | 0.59 (32) | 0.94 (32) | 0.94 (17) | 0.99 | 0.96 |
| 13 Nov | Slice | 01:16 | $0.339 | 0.50 (32) | 0.88 (32) | 0.93 (15) | 0.99 | 1.00 |
| 14 Nov | Slice | 00:56 | $0.335 | 0.56 (32) | 0.91 (32) | 0.81 (16) | 1.00 | 1.00 |
| 15 Nov | Full, cut short | 00:00 | $0.561 | 0.61 (70) | 0.93 (70) | 0.86 (36) | 1.00 | 1.00 |
| 16 Nov | Slice | 00:04 | $0.353 | 0.62 (32) | 0.94 (32) | 0.94 (17) | 0.99 | 1.00 |
| 17 Nov | Slice | 03:01 | $0.339 | 0.62 (32) | 0.94 (32) | 0.82 (17) | 0.99 | 1.00 |
| 18 Nov | Slice | 02:30 | $0.362 | 0.66 (32) | 0.94 (32) | 0.71 (17) | 0.99 | 1.00 |
| 19 Nov | Slice | 01:56 | $0.355 | 0.56 (32) | 0.91 (32) | 0.81 (16) | 1.00 | 1.00 |
| 20 Nov | Slice | 01:49 | $0.351 | 0.62 (32) | 0.94 (32) | 0.71 (17) | 1.00 | 1.00 |
| 21 Nov | Slice | 01:38 | $0.342 | 0.56 (32) | 0.94 (32) | 0.83 (18) | 0.99 | 0.96 |
| 22 Nov | Full | 00:32 | $0.756 | 0.66 (100) | 0.91 (100) | 0.77 (52) | 0.99 | 1.00 |
| 23 Nov | Slice | 01:00 | $0.357 | 0.62 (32) | 1.00 (32) | 0.79 (19) | 1.00 | 1.00 |

Routing covers the routing set's 138 dev questions each night, and SQL the SQL set's 28.

- **The slices cost as sized:** ten slices to 23 November cost $0.335 to $0.362, against the estimate of about $0.33, and their answers steps spent $0.156 to $0.179 of their $0.20 share. No step reached its cap.
- **The same 32 questions scored 0.50 to 0.66 correct.** Fresh calls vary from night to night, and these differences are within the intervals. No night before 23 November drew a verdict: the first baseline is the full night of 22 November (below).
- **GitHub starts the nights late:** 3.5 to 6.5 hours after 20:30 UTC.

## The first full night was cut short

- **What happened.** On 15 November the answers step stopped at question 71 of 100. It exited 1 with no exception in its log, which is how `run_copilot.py` ends when a model call fails after its retries. The other four steps finished, and the night spent $0.56 of its $1.20. It was kept as partial, so it drew no verdict and didn't become the baseline.
- **The likely cause: the small role's free quota.** Groq allows gpt-oss-20b about 200K tokens in any 24 hours.
  - **A full night's need.** The copilot uses about 1.7K of them a question (copilot v2's 100 dev questions used 117,807 prompt and 56,014 completion tokens), so a full night needs about 174K.
  - **What else was in the window.** Saturday's slice (about 52K; GitHub had started it at 00:56 UTC) and the live demo's calls, the canary's trial among them.
  - **When it stopped.** The night had used about 105K, 12 minutes before Saturday's slice began to leave the window.
  - **The provider's message stayed on the runner,** in the step's log.
- **The fix: wait, with the same models (#119).** A step a model stops now exits 75 and runs again every ten minutes, for up to three hours a night, carrying on where it stopped. Production's fallback would have sent the small role to Cerebras's gpt-oss-120b, a different model, and a night is compared question by question with the baseline.
- **The baseline is now the full night of 22 November,** so slices draw verdicts from 23 November.

## The first baseline: the full night of 22 November

The full night answered all 100 dev questions and became the baseline (`nightly/latest-full.json`).

- **It waited twice.** A model stopped its answers step twice, and each time the step ran again ten minutes later and carried on (#119). The step took 90 minutes, and the night 1 hour 50 minutes. The step's log stays on the runner, so the cause isn't recorded. Most likely it was Groq's daily quota for the small role again: the night began 23 hours after Saturday's slice, whose calls were still in Groq's 24-hour window.
- **The cost:** $0.756 of $1.20, against the estimate of about $0.75. Cerebras billed $0.731 ($0.409 for gpt-oss-120b and $0.322 for Qwen), and Groq's small role came to $0.025 at list price. An answer cost $0.0049 on average.

| Metric | Full night | 95% interval | Questions |
|---|---|---|---|
| Correct | 0.66 | 0.57 to 0.75 | 100 |
| Answered | 0.91 | 0.85 to 0.96 | 100 |
| Faithful, doc and hybrid answers | 0.77 | 0.65 to 0.88 | 52 |
| Routing accuracy | 0.99 | 0.95 to 1.00 (exact) | 138 |
| SQL accuracy | 1.00 | 0.88 to 1.00 (exact) | 28 |

- **The same level as copilot v2.** Copilot v2 answered 0.65 of the same 100 questions correctly on the laptop, on the same provider and judges ([report](copilot-v2.md)).

## The first verdict: 23 November

23 November's slice was the first night tested against the baseline, on the 32 questions both nights answered. No metric dropped:

| Metric | Baseline | Night | Difference | 95% interval | p (Holm) |
|---|---|---|---|---|---|
| Correct | 0.656 | 0.625 | −0.031 | −0.156 to +0.094 | 1.0 |
| Answered | 0.938 | 1.000 | +0.062 | 0.000 to +0.156 | 1.0 |
| Routing accuracy (138) | 0.986 | 1.000 | +0.014 | 0.000 to +0.036 | 1.0 |
| SQL accuracy (28) | 1.000 | 1.000 | 0.000 | 0.000 to 0.000 | 1.0 |

On 32 questions a drop must reach about 25 points to show (Limits below), so this verdict says the night didn't break, not that nothing moved.

## Decision: the small role stays on Groq

The full night needed most of Groq's free daily quota for gpt-oss-20b, as expected, and waited twice for twenty minutes in all. On 16 November the owner had approved paid Cerebras for evaluation runs, if the full night of 22 November was cut short. It wasn't, so the nights keep Groq's free tier for the small role:

- **It is production's model.** The deployed copilot runs its small role on Groq's gpt-oss-20b. Cerebras doesn't serve that model, so moving the role there would mean gpt-oss-120b, which production calls only as its paid fallback.
- **The waiting works.** A full night has three hours of waiting, and the first needed twenty minutes.
- **The slices keep their margin.** On Cerebras's gpt-oss-120b, the small role would add about $0.02 to a slice, and a typical slice would then cost about $0.37, 93% of its cap.

If a full night is cut short again, the approved fallback stands: the small role moves to Cerebras's gpt-oss-120b for every night, the slice shrinks if the cap needs it, and a full night run by hand (at most $1.20) becomes the new baseline.

## Limits

- **One night.** The cost of a night varies with the length of the models' replies, and the first scheduled nights will show by how much. If a night is cut short, the slice shrinks again.
- **A 32-question slice detects only large drops.** With the night's four tests adjusted together, a drop is significant only when at least 8 of the 32 questions change, all the same way: 25 points. On the Sunday run's 100 questions, 8 points can show. The slice's nights show the trend and catch a breakage; the full run is the finer test.
- **The judges are models.** Their verdicts carry the caveats of [the judge guide](../concepts/llm-as-judge.md); the same judges grade every night, so the trend compares like with like.
- **The interval on faithfulness is wide,** since only the doc and hybrid answers cite pages (21 of 40).
- **A Sunday needs most of a day's free quota.** A full night (about 174K tokens) and a day's canary (about 20K) come close to Groq's 200K for the small model, and the full night of 22 November waited twice. Heavy use of the demo the day before can still cut a full night short, and it then draws no verdict.
