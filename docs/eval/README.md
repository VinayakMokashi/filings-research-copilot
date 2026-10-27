# Evaluation reports

| Report | Phase | Question |
|---|---|---|
| [Retrieval baseline](retrieval-baseline.md) | 2 | Which chunking, search mode, reranker and context expansion to start from |
| [Doc agent: dev evaluation](doc-agent-dev.md) | 3 | How often the doc agent answers correctly from filing text, how well its citations hold up, what it costs, and where the wrong answers come from |
| [Data agent: FinanceBench's metrics questions](data-agent-financebench.md) | 4 | Whether SQL over the facts database answers FinanceBench's figure questions better than reading filing pages, and at what cost |
| [Hybrid answers: a prototype](hybrid-prototype.md) | 4 | Whether one answer can take its figures from the data agent and its reasons from the filings, and how that compares with the doc agent alone |
| [Hybrid answers, version 2](hybrid-v2.md) | 5 | Whether routing by need, a question split, partial answers and a retry answer the hybrid questions the prototype refused, and at what cost |
| [The validator loop: dev evaluation](validator-dev.md) | 5 | Whether checking every cited sentence and revising what fails makes the doc agent's answers faithful without costing correctness, and at what cost |
| [Self-consistency on figure answers](self-consistency.md) | 5 | Whether sampling more answers to a figure question and voting on the figure makes the doc agent's figure answers correct more often, and whether that pays for its cost |
| [The copilot end to end: dev evaluation](copilot-dev.md) | 5 | Whether the whole copilot, routing each question to the doc, data or hybrid agent and checking what they write, answers FinanceBench's dev questions better than the doc agent alone, and at what cost in steps, money and time |
| [A LoRA classifier as the router](lora-router.md) | 7 | Whether a small encoder fine-tuned with LoRA on the LLM router's labels routes nearly as well as it, on the CPU and at no cost, alone, in a cascade or as the fallback |
| [The copilot's version 2: dev evaluation](copilot-v2.md) | 7 | Whether handing declined questions on to the doc agent, routing by the database's grain and letting a checked answer keep a labelled assessment win back the questions the first version lost to the doc agent alone |
| [Bandit routing between answer models](bandit-routing.md) | 7 | Whether an ε-greedy or UCB1 bandit, learning from each answer's reward less a cost penalty, chooses between answer models better than one fixed model |
| [DSPy on the HyDE prompt](dspy-hyde.md) | 7 | Whether DSPy's MIPROv2 finds a HyDE instruction whose passages rank the evidence higher than the hand-written prompt's |
| [A domain embedder, fine-tuned on filings](domain-embedder.md) | 7 | Whether bge-small fine-tuned with hard negatives on synthetic questions about training filings ranks FinanceBench's evidence pages higher in the doc agent's search |
| [Routing: semantic and LLM routers](routing.md) | 5 | Which router should choose each question's route, by embedding similarity, by asking a model, or both, and at what latency and cost |

One report per experiment, with these sections:

1. **Question:** what we're trying to find out.
2. **Setup:** data, configuration, models, seeds.
3. **Results:** every metric with a 95% bootstrap confidence interval.
4. **Comparison:** the paired difference against the current baseline, and whether it is significant.
5. **Decision:** adopt or reject, with a link to the ADR.
6. **Logs:** where the raw per-question logs live.

## Datasets and splits

| Set | Size | Where | Rule |
|---|---|---|---|
| FinanceBench dev | 100 questions, 20 companies | [`eval/financebench/splits.json`](../../eval/financebench/splits.json) | Used for all tuning and comparisons |
| FinanceBench test | 50 questions, 12 companies | Same file | Held out: opened only at milestones, and each report says whether it was ([ADR-0006](../decisions/0006-evaluation-splits.md)) |
| Routing dev | 138 questions, 46 seeds | [`eval/routing/queries.jsonl`](../../eval/routing/queries.jsonl) | Used for tuning routers ([data card](../data/routing-set.md)) |
| Routing test | 60 questions, 20 seeds | Same file | Held out, like FinanceBench test; opened once, at Phase 5's milestone |
| SQL dev | 28 questions (21 answerable) | [`eval/sql/questions.jsonl`](../../eval/sql/questions.jsonl) | Used for tuning the data agent ([data card](../data/sql-set.md)) |
| SQL test | 14 questions (11 answerable) | Same file | Held out |
| Memory set | 20 turns, 10 conversations, 6 users | [`eval/memory/`](../../eval/memory/) | Used for the memory checks ([data card](../data/memory-set.md)); no held-out side |

## Runs

Each run writes `items.jsonl`, `summary.json` and `summary.md` to `eval/results/<suite>/<run>/<split>/`. Intervals and tests follow [ADR-0007](../decisions/0007-evaluation-statistics.md); the [runbook](../runbooks/running-evaluations.md) shows the commands.

| Run | Suite | Split | Headline (95% interval) | What it is |
|---|---|---|---|---|
| [first-pages](../../eval/results/retrieval/first-pages/dev/summary.md) | Retrieval | Dev | hit@20 0.29 (0.20 to 0.38) | Floor: the first 20 pages of the correct document |
| [page_bge-small-dense-oracle](../../eval/results/retrieval/page_bge-small-dense-oracle/dev/summary.md) | Retrieval | Dev | recall@10 0.630 (0.54 to 0.72); MRR@10 0.423 | Dense search over page chunks within the question's filing: the baseline ([ADR-0011](../decisions/0011-retrieval-baseline.md)) |
| [page_bge-small-dense-corpus](../../eval/results/retrieval/page_bge-small-dense-corpus/dev/summary.md) | Retrieval | Dev | recall@10 0.415 (0.33 to 0.51); MRR@10 0.230 | The same across all 84 filings |
| [page_bge-small-dense-understood](../../eval/results/retrieval/page_bge-small-dense-understood/dev/summary.md) | Retrieval | Dev | recall@10 0.570 (0.48 to 0.67); MRR@10 0.381 | Searching the filings resolved from each question's company, period and form ([guide](../concepts/query-understanding.md)) |
| [page_bge-small-dense-rw-multi-hyde-decompose-understood](../../eval/results/retrieval/page_bge-small-dense-rw-multi-hyde-decompose-understood/dev/summary.md) | Retrieval | Dev | recall@10 0.722 (0.63 to 0.81); MRR@10 0.476 | The same, plus multi-query, HyDE and decomposition rewrites, fused: the doc agent's retrieval ([ADR-0012](../decisions/0012-query-understanding-and-rewriting.md)) |
| [tokens-480_bge-small-dense-oracle](../../eval/results/retrieval/tokens-480_bge-small-dense-oracle/dev/summary.md) | Retrieval | Dev | recall@10 0.608 (0.52 to 0.70); MRR@10 0.307 | Dense search over 480-token chunks, the comparison point for the variants |
| [Other retrieval runs](../../eval/results/retrieval/) | Retrieval | Dev | See the [report](retrieval-baseline.md) | BM25, hybrid, rerankers, neighbouring chunks, chunking, late chunking |
| [page-rw-all-understood-b3000](../../eval/results/context/page-rw-all-understood-b3000/dev/summary.md) | Context | Dev | context_hit 0.68 (0.59 to 0.77) | An evidence page among the answer's sources: 3,000 tokens of the agent's retrieval ([ADR-0013](../decisions/0013-answer-format.md)); the other budgets sit [beside it](../../eval/results/context/) |
| [doc-agent-v3](../../eval/results/answers/doc-agent-v3/dev/summary.md) | Answers | Dev, first 10 | answered 0.90 (0.70 to 1.00); evidence cited 0.50 (0.20 to 0.80) | Smoke run of the doc agent; v1 and v2 are the runs before the citation and retry fixes ([ADR-0013](../decisions/0013-answer-format.md)) |
| [doc-agent-v4-full--qwen3.8-27b-p2](../../eval/results/correctness/doc-agent-v4-full--qwen3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.65 (0.56 to 0.74); refused 0.06 | The Phase 3 doc agent graded by the default judge ([report](doc-agent-dev.md)); v3 and the second judge sit beside it |
| [doc-agent-v4-validated--qwen3.8-27b-p2](../../eval/results/correctness/doc-agent-v4-validated--qwen3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.61 (0.51 to 0.71); refused 0.08 | The doc agent's answers after the validator loop ([report](validator-dev.md)) |
| [doc-agent-v4-validated--qwen3.8-27b-f1](../../eval/results/faithfulness/doc-agent-v4-validated--qwen3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 92 answered | faithful 0.85 (0.77 to 0.92); supported 0.91 | The same answers, each sentence checked against the pages it cites |
| [doc-agent-v4-sc3--qwen3.8-27b-p2](../../eval/results/correctness/doc-agent-v4-sc3--qwen3.8-27b-p2/dev/summary.md) | Correctness | Dev, 33 figure questions | correct 0.88 (0.76 to 0.97), as before voting | The doc agent's figure answers after a vote of three, the stored answer and two samples ([report](self-consistency.md)) |
| [doc-agent-v4-full--qwen3.8-27b-f1](../../eval/results/faithfulness/doc-agent-v4-full--qwen3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 94 answered | faithful 0.63 (0.53 to 0.72); citation precision 0.93 | Each sentence checked against the pages it cites |
| [doc-agent-v4-full--qwen-3.8-27b-p2](../../eval/results/correctness/doc-agent-v4-full--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.64 (0.55 to 0.73); refused 0.06 | The Phase 3 doc agent graded by the answer judge on Cerebras: the baseline for runs judged there ([ADR-0024](../decisions/0024-second-provider.md)) |
| [doc-agent-v4-full--qwen-3.8-27b-f1](../../eval/results/faithfulness/doc-agent-v4-full--qwen-3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 94 answered | faithful 0.62 (0.52 to 0.71); citation precision 0.96 | The same answers checked on Cerebras |
| [copilot-v2--qwen-3.8-27b-p2](../../eval/results/correctness/copilot-v2--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.65 (0.56 to 0.74); refused 0.09 | The copilot's version 2, on Cerebras ([report](copilot-v2.md)) |
| [copilot-v2-drafts--qwen-3.8-27b-p2](../../eval/results/correctness/copilot-v2-drafts--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.67 (0.58 to 0.76); refused 0.07 | Version 2's first answers, before the validator |
| [copilot-v2--qwen-3.8-27b-f1](../../eval/results/faithfulness/copilot-v2--qwen-3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 91 answered | faithful 0.50; 0.82 (0.71 to 0.91) on the 55 doc and hybrid answers | The check can't read the data agent's answers |
| [copilot-v2](../../eval/results/copilot/copilot-v2/dev/summary.md) | Agent metrics | Dev | 8.8 steps; tool success 1.00; handed on 0.04; revised 0.28; $0.0050 a question | Version 2's routes, handoffs, revisions and cost |
| [llm-r2-gpt-oss-120b-cerebras](../../eval/results/routing/llm-r2-gpt-oss-120b-cerebras/dev/summary.md) | Routing | Dev | accuracy 1.000 (exact 0.974 to 1.000) | Router prompt r2, with the rules on the database's grain, on Cerebras ([ADR-0026](../decisions/0026-copilot-v2.md)) |
| [copilot-v1--qwen-3.8-27b-p2](../../eval/results/correctness/copilot-v1--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.49 (0.39 to 0.59); refused 0.18 | The whole copilot, on Cerebras ([report](copilot-dev.md)) |
| [copilot-v1-drafts--qwen-3.8-27b-p2](../../eval/results/correctness/copilot-v1-drafts--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.55 (0.45 to 0.65); refused 0.14 | The specialists' first answers in the same run, before the validator |
| [doc-agent-v4-cerebras--qwen-3.8-27b-p2](../../eval/results/correctness/doc-agent-v4-cerebras--qwen-3.8-27b-p2/dev/summary.md) | Correctness | Dev | correct 0.65 (0.55 to 0.74); refused 0.07 | The doc agent alone, answered again on Cerebras: the copilot's same-provider baseline |
| [copilot-v1--qwen-3.8-27b-f1](../../eval/results/faithfulness/copilot-v1--qwen-3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 82 answered | faithful 0.39 (0.28 to 0.50); 0.76 on the 42 doc and hybrid answers | The check can't read the data agent's answers, which cite the database rather than pages |
| [copilot-v1-drafts--qwen-3.8-27b-f1](../../eval/results/faithfulness/copilot-v1-drafts--qwen-3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 86 answered | faithful 0.24 (0.15 to 0.34); 0.48 on the same 42 | The drafts, before the validator |
| [doc-agent-v4-cerebras--qwen-3.8-27b-f1](../../eval/results/faithfulness/doc-agent-v4-cerebras--qwen-3.8-27b-f1/dev/summary.md) | Faithfulness | Dev, 93 answered | faithful 0.62 (0.53 to 0.72); citation precision 0.94 | The doc agent alone on Cerebras |
| [copilot-v1](../../eval/results/copilot/copilot-v1/dev/summary.md) | Agent metrics | Dev | 8.7 steps; tool success 1.00; revised 0.26; $0.0047 a question | Routes, steps, revisions, cost and time, by route and question type |
| [copilot-v1 latency](../../eval/results/latency/copilot-v1.json) | Latency | Dev | median data 17.8 s, doc 40.2 s, hybrid 52.8 s | From the run's trace; batch pauses included |
| [doc-agent-v4-full--qwen3.8-27b-p2](../../eval/results/errors/doc-agent-v4-full--qwen3.8-27b-p2/dev/summary.md) | Errors | Dev | 18 wrong with the evidence in context; 11 without | Error categories, model latency and cost |
| [doc-agent-v3-full--qwen3.8-27b-p2](../../eval/results/judge-agreement/doc-agent-v3-full--qwen3.8-27b-p2/dev/summary.md) | Judge agreement | Dev, 41 labelled | agree 1.00; kappa 1.00 | The default answer judge against reference labels from a stronger model ([ADR-0014](../decisions/0014-answer-judge.md)) |
| [doc-agent-v3-full--gpt-oss-20b-p2](../../eval/results/judge-agreement/doc-agent-v3-full--gpt-oss-20b-p2/dev/summary.md) | Judge agreement | Dev, 41 labelled | agree 0.93 (0.83 to 1.00); kappa 0.84 (0.63 to 1.00) | The second judge against the same labels |
| [doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2](../../eval/results/judge-agreement/doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2/dev/summary.md) | Judge agreement | Dev, 100 | agree 0.99 (0.97 to 1.00); kappa 0.98 (0.93 to 1.00) | The answer judge on Groq against the same model on Cerebras, reasoning off ([ADR-0024](../decisions/0024-second-provider.md)) |
| [doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1](../../eval/results/judge-agreement/doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1/dev/summary.md) | Judge agreement | Dev, 94 answered | agree 0.97 (0.93 to 1.00); kappa 0.93 (0.85 to 1.00) | The faithfulness check on the two providers |
| [doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2-reasoning-high](../../eval/results/judge-agreement/doc-agent-v4-full--qwen3.8-27b-p2--vs--qwen-3.8-27b-p2-reasoning-high/dev/summary.md) | Judge agreement | Dev, 100 | agree 0.94 (0.89 to 0.98); kappa 0.88 (0.78 to 0.96) | The same with Cerebras's default reasoning: 9 verdicts cut off before their JSON |
| [doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1-reasoning-high](../../eval/results/judge-agreement/doc-agent-v4-full--qwen3.8-27b-f1--vs--qwen-3.8-27b-f1-reasoning-high/dev/summary.md) | Judge agreement | Dev, 94 answered | agree 0.83 (0.76 to 0.90); kappa 0.66 (0.50 to 0.81) | The faithfulness check with Cerebras's default reasoning: 31 replies cut off |
| [data-agent-v1--qwen3.8-27b-p2](../../eval/results/correctness/data-agent-v1--qwen3.8-27b-p2/dev/summary.md) | Correctness | Dev, 33 metrics | correct 0.97 (exact 0.84 to 1.00) | The data agent on FinanceBench's metrics questions, against the doc agent's 0.88 on the same questions ([report](data-agent-financebench.md)); the second judge sits beside it |
| [data-agent-v1](../../eval/results/answers/data-agent-v1/dev/summary.md) | Answers | Dev, 33 metrics | answered 1.00; repaired 0.03 | That run: no declines or failures; tokens, model latency and cost |
| [hybrid-v2](../../eval/results/hybrid/hybrid-v2/dev/summary.md) | Hybrid | 13 own questions | every figure 13 of 13; faithful 0.54 (0.23 to 0.77) | Version 2: routed by need, the question split, partial answers and a retry; the graph's hybrid node ([report](hybrid-v2.md)) |
| [hybrid-v1](../../eval/results/hybrid/hybrid-v1/dev/summary.md) | Hybrid | 13 own questions | every figure 10 of 13; faithful 0.62 (0.38 to 0.85) | The hybrid agent: the data agent's figures and the doc agent's pages in one cited answer ([report](hybrid-prototype.md)) |
| [doc-agent-v4](../../eval/results/hybrid/doc-agent-v4/dev/summary.md) | Hybrid | 13 own questions | every figure 10 of 13; faithful 0.46 (0.23 to 0.69) | The doc agent alone on the same questions |
| [sql-agent-v2, test](../../eval/results/sql/sql-agent-v2/test/summary.md) | SQL | Test, held out, opened once | accuracy 1.000 (exact 0.77 to 1.00) | The data agent with value linking on the 14 held-out questions, at the close of Phase 4 |
| [sql-agent-v2](../../eval/results/sql/sql-agent-v2/dev/summary.md) | SQL | Dev | accuracy 1.000 (exact 0.88 to 1.00) | The data agent with value linking ([guide](../concepts/value-linking.md)) |
| [sql-agent-v1](../../eval/results/sql/sql-agent-v1/dev/summary.md) | SQL | Dev | accuracy 0.607 (0.43 to 0.79) | The data agent: text2sql-analyst over the facts database, before value linking ([ADR-0015](../decisions/0015-reuse-text2sql-analyst.md)) |
| [classifier-v2, test](../../eval/results/routing/classifier-v2/test/summary.md) | Routing | Test, held out, scored once for this model | accuracy 0.950 (0.883 to 1.000) | The final classifier router ([report](lora-router.md)) |
| [classifier-v2](../../eval/results/routing/classifier-v2/dev/summary.md) | Routing | Dev | accuracy 0.913 (0.862 to 0.957); 8 ms on the CPU | bge-small with LoRA, trained on the second training set: the LLM router's fallback ([ADR-0025](../decisions/0025-classifier-router.md)) |
| [classifier-v1](../../eval/results/routing/classifier-v1/dev/summary.md) | Routing | Dev | accuracy 0.833 (0.768 to 0.891) | The same, trained on the first set, which left out most kinds of decline |
| [cascade-classifier-v2-t0.8](../../eval/results/routing/cascade-classifier-v2-t0.8/dev/summary.md) | Routing | Dev and test | accuracy 0.957 (dev), 0.967 (test); 9% and 5% sent to the LLM router | The classifier's route above 0.8 confidence, the LLM router's below; the other thresholds sit [beside it](../../eval/results/routing/_comparisons/cascade-classifier-v2-dev.md) |
| [llm-gpt-oss-120b, test](../../eval/results/routing/llm-gpt-oss-120b/test/summary.md) | Routing | Test, held out, opened once | accuracy 1.000 (exact 0.940 to 1.000) | The copilot's router on the 60 held-out questions, at Phase 5's milestone ([report](routing.md#the-test-split)) |
| [semantic-masked-centroid, test](../../eval/results/routing/semantic-masked-centroid/test/summary.md) | Routing | Test, held out, opened once | accuracy 0.800 (0.700 to 0.900) | The fallback router on the same questions; the keyword rules (0.650) and the majority route (0.250) sit [beside it](../../eval/results/routing/) |
| [llm-gpt-oss-120b](../../eval/results/routing/llm-gpt-oss-120b/dev/summary.md) | Routing | Dev | accuracy 1.000 (exact 0.974 to 1.000) | The LLM router on the strong model, prompt r1: the copilot's router ([ADR-0017](../decisions/0017-routing.md)) |
| [llm-gpt-oss-20b](../../eval/results/routing/llm-gpt-oss-20b/dev/summary.md) | Routing | Dev | accuracy 0.964 (0.928 to 0.993) | The same prompt on gpt-oss-20b |
| [llm-qwen3.8-27b](../../eval/results/routing/llm-qwen3.8-27b/dev/summary.md) | Routing | Dev | accuracy 1.000 (exact 0.974 to 1.000) | The same prompt on Qwen3.8 27B, the fast role, at four times the cost |
| [semantic-masked-centroid](../../eval/results/routing/semantic-masked-centroid/dev/summary.md) | Routing | Dev | accuracy 0.739 (0.667 to 0.812) | bge-small, companies and years masked, nearest route centroid, each seed group left out: the fallback router; the other semantic variants sit [beside it](../../eval/results/routing/) |
| [semantic-k5](../../eval/results/routing/semantic-k5/dev/summary.md) | Routing | Dev | accuracy 0.391 (0.312 to 0.471) | The first semantic design: a vote of the five nearest examples |
| [majority](../../eval/results/routing/majority/dev/summary.md) | Routing | Dev | accuracy 0.217 (0.152 to 0.290) | Always the most common route |
| [keyword](../../eval/results/routing/keyword/dev/summary.md) | Routing | Dev | accuracy 0.623 (0.543 to 0.703) | Floor: hand-written keyword rules |
| [memory-v2](../../eval/results/memory/memory-v2/dev/summary.md) | Memory | 20 turns | resolved 1.000; notes checks 15 of 15 | Follow-up rewriting and notes prompt 2: only what users say about themselves ([guide](../concepts/agent-memory.md)) |
| [memory-v1](../../eval/results/memory/memory-v1/dev/summary.md) | Memory | 20 turns | resolved 1.000; notes checks 7 of 15 | Notes prompt 1, which turned questions into notes |
| [corpus-scan](../../eval/results/injection/corpus-scan.json) | Injection | All 366 parsed filings | 0 of 53,901 pages flagged | The prompt-injection patterns over the whole corpus ([guide](../concepts/prompt-injection.md)) |
| [similarity cache, dev](../../eval/results/cache/similarity/dev/summary.md) | Cache | Routing dev pairs | at 0.95: 16 of 81 paraphrase pairs hit, 42 of 104 measure swaps | A semantic cache would serve swapped measures more often than paraphrases ([guide](../concepts/semantic-cache.md)) |
| [similarity cache, test](../../eval/results/cache/similarity/test/summary.md) | Cache | Routing test pairs | at 0.95: 7 of 39 paraphrase pairs hit, 29 of 52 measure swaps | The same on the test side |
| [financebench-dev-checks](../../eval/results/facts/financebench-dev-checks.md) | Facts database | Dev | 33 of 33 agree exactly | FinanceBench metrics questions as formulas over annual values |
| [gold](../../eval/results/sql/gold/dev/summary.md) | SQL | Dev | accuracy 1.000 | Gold SQL: a check of the scorer |
| [decline-all](../../eval/results/sql/decline-all/dev/summary.md) | SQL | Dev | accuracy 0.250 (0.107 to 0.429) | Floor: decline everything |
