# ADR-0013: Answer from numbered sources in JSON, with a calculator and one retry aimed at what is missing

- **Status:** Accepted
- **Date:** 2026-10-19
- **Phase:** 3

## Context

ADR-0012 puts an evidence page in the top 10 search results for most dev questions. The answer step turns those pages into an answer a reader can check, and it has four jobs:

1. **State only what the filings say, and show where.** A reader should be able to open the PDF page behind every figure.
2. **Get the arithmetic right.** A third of FinanceBench's dev questions are metrics-generated: ratios, margins and growth rates computed from two or three line items. A model that reads the right figures can still divide them wrong.
3. **Say so when the evidence isn't there**, instead of filling the gap from memory. A figure the sources don't contain can't be cited, even when the model happens to know it.
4. **Fit the free tier:** about 200,000 tokens a day on the strong model, and 8,000 a minute.

## Options considered

| Question | Options |
|---|---|
| Context | 1,500, 3,000 or 4,500 tokens of the best chunks; with or without the other parts of split pages; reranked or in fused order |
| Answer format | Free text with citations; one JSON object with the answer, its calculations and whether the sources suffice |
| Arithmetic | The model computes; a tool-calling loop with a calculator; expressions returned with the answer, evaluated afterwards and filled into placeholders |
| Missing evidence | Always answer; abstain; abstain after one more search |
| Checking the evidence | Grade each source with a model call before answering, as in corrective RAG; let the answer call decide whether the sources suffice |

## Decision

1. **Context** (`copilot.answer.context`): the best chunks in fused rank order, numbered and labelled with company, form, period and PDF page ("3M, Form 10-K for fiscal 2018, PDF page 60"), up to 3,000 tokens. A chunk that doesn't fit is skipped and smaller ones after it still go in. No split-page parts and no reranking (ADR-0012).
2. **One answer call** (`copilot.answer.generate`): the strong model at temperature 0 in JSON mode returns `answerable`, `answer` (every factual sentence ending with [n] citations), `calculations` and `missing`. The reply is parsed leniently and validated against a schema; a reply that fails becomes an unanswerable answer with the error recorded. Citations in lenticular brackets ("【2】") are rewritten as [2]; citations to numbers that aren't sources are recorded as invalid.
3. **The calculator** (`copilot.answer.calculator`): the model writes each computation as an expression over numbers from the sources, with an id and the decimals to show. The expression is cleaned (thousands separators, currency signs, percentages) and evaluated by the facts database's formula parser, which allows numbers and `+ - * /` only, and the result replaces `{c1}` in the answer. One call returns everything, so a calculation costs no extra round trip, unlike a tool-calling loop.
4. **Abstention, with one retry aimed at the gap** (`copilot.answer.agent`): when the model says the sources fall short, it names the missing facts with their line items and periods. The agent searches for that text across all of the company's filings, alongside the original searches and weighted as much as all of them together, packs a second context half as large again (4,500 tokens) so the new pages join the old ones instead of replacing them, and asks once more. A second refusal is final.
5. **The relevance check is the answer call's own verdict**: `answerable` judges the sources as a whole, with no separate grading call per source.

## Evidence

Context: how often an evidence page is among the sources, 100 dev questions, with ADR-0012's retrieval ([comparison](../../eval/results/context/_comparisons/budget-context-hit.md)):

| Budget (tokens) | Sources (mean) | Evidence page in context | Against 3,000 (Holm-adjusted) |
|---|---|---|---|
| 1,500 | 4.2 | 0.52 | −0.16, p = 0.0006 |
| **3,000** | **8.2** | **0.68** (0.59 to 0.77) | |
| 4,500 | 11.8 | 0.73 | +0.05, p = 0.064 |
| 3,000, split pages completed | 9.2 | 0.61 | −0.07, p = 0.030 |

- 4,500 tokens would add half as much again to every answer's cost for a gain that isn't significant. Completing split pages spends the budget on text next to a hit instead of on the next-ranked hit.
- By question type at 3,000 tokens: metrics-generated 0.91, domain-relevant 0.59, novel-generated 0.55.

Smoke runs on the first ten dev questions (structural measures only; correctness needs the judge of step 3.6):

| Run | Answered | Retried | Uncited | Evidence in context | Evidence cited | Invalid citations | Failed calculations | Prompt tokens (mean) |
|---|---|---|---|---|---|---|---|---|
| [v1](../../eval/results/answers/doc-agent-v1/dev/summary.md): prompt 1, retry only into wider filings | 8 | 0 | 3 | 5 | 2 | 0 | 0 | 3,839 |
| [v2](../../eval/results/answers/doc-agent-v2/dev/summary.md): prompt 2, retry aimed at what is missing | 9 | 2 | 1 | 7 | 5 | 0 | 0 | 4,672 |
| [v3](../../eval/results/answers/doc-agent-v3/dev/summary.md): v2 with a 4,500-token retry context | 9 | 2 | 1 | 7 | 5 | 0 | 0 | 5,037 |

- Counts are out of ten questions. "Uncited" is an answer with no valid citation: in v1, one answer cited in lenticular brackets and two cited nothing.
- v1's retry never ran: both refusals were about a company with a single filing in the corpus. v2's retry ran for both and brought an evidence page into the context each time.
- The step from v2 to v3 doesn't show in these measures, only in the answers: at 3,000 tokens the pages found for the gap pushed out the income statement, so one retried answer computed its ratio from the wrong figure. At 4,500 tokens it has both pages and matches the reference answer. The other retried question still lacks its revenue page and refuses, which an offline run of the same searches says would need 6,000 tokens.
- Ten questions are a smoke test, not an evaluation: intervals on these shares are up to ±0.3 wide. The dev evaluation (step 3.7) runs all 100.

## Consequences

- A first answer costs about 3,800 prompt tokens and a few hundred completion tokens, and a retried one about 10,000 in all. With retries, the smoke runs averaged about 5,700 tokens a question, so the free tier answers about 35 questions a day on one strong model; the dev run of 100 questions needs about three days, or a second provider.
- One smoke answer in ten still cited nothing. If the dev run shows that often, the remedy is a repair call that returns the reply to the model with the missing citations named; until then it is counted, not fixed.
- `answerable` folds "the sources don't say" and "the filing doesn't say" together. The retry recovers the first case; the second stays a refusal, which is the right answer.
- Cited pages are compared with FinanceBench's evidence pages, which makes "an evidence page is among the cited sources" a lower bound: a figure often appears on several pages (the income statement and a segment note, the 10-K and the earnings release).
- The calculator only sees what the model writes. A misread figure is computed exactly and is still wrong, so correctness is measured on the final answer (step 3.6).

## References

- Gao et al., [Enabling Large Language Models to Generate Text with Citations](https://arxiv.org/abs/2305.14627), 2023.
- Gao et al., [PAL: Program-aided Language Models](https://arxiv.org/abs/2211.10435), 2022.
- Yan et al., [Corrective Retrieval Augmented Generation](https://arxiv.org/abs/2401.15884), 2024.
- Asai et al., [Self-RAG](https://arxiv.org/abs/2310.11511), 2023.
- Guides: [grounded generation](../concepts/grounded-generation.md), [corrective RAG](../concepts/corrective-rag.md).
