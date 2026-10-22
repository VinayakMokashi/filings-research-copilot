# Grounded generation

> Answer only from numbered sources, cite them sentence by sentence, leave the arithmetic to a calculator, and say so when the sources fall short.

**Lands in:** Phase 3 · **Code:** `src/copilot/answer/`

## What it is

A **grounded** answer is one whose every claim can be traced to a passage the system retrieved. "3M's capital expenditure was $1,577 million in fiscal 2018 [3]" is grounded when source [3] says so. The same sentence written from the model's memory is not, even when it happens to be right, because nobody can check it against what the system read.

Grounded generation is the last step of retrieval-augmented generation (RAG): the model gets the question and a set of numbered sources, and writes an answer that cites them. Three habits make the answers trustworthy:

- **Citations.** Every factual sentence names the sources it rests on, as [n].
- **Abstention.** If the sources don't contain what the question needs, the model says so and names what is missing, instead of guessing.
- **Arithmetic outside the model.** The model writes the calculation; a calculator does it.

## Why we need it here

An analyst can't use a figure they can't verify. Citations make every answer checkable against a PDF page, and the rule "only from the sources" turns a retrieval miss into a visible refusal instead of a confident, unverifiable number.

FinanceBench makes the arithmetic matter. A third of its dev questions are *metrics-generated*: a ratio, margin or growth rate computed from two or three line items, often from different statements. A model that reads the right figures can still divide them wrong, and a wrong digit in a ratio makes the answer wrong.

## How it works

```mermaid
flowchart LR
    Q["Question"] --> R["Retrieve<br/>resolved filings, rewrites, fused search"]
    R --> C["Context<br/>numbered sources, 3,000 tokens"]
    C --> M["Answer model<br/>one JSON object"]
    M --> K["Calculator<br/>fills {c1}"]
    K --> V["Citation check"]
    V --> A["Answer with its sources"]
```

1. **Numbered sources** (`pack`, `describe`). The retrieved chunks go into the prompt in rank order, each with a number and a label a reader can follow:

   ```
   [3] 3M, Form 10-K for fiscal 2018, PDF page 60
   ...the page text...
   ```

   Pages in the label count from one, the way a PDF viewer shows them; FinanceBench and the index count from zero.
2. **The budget.** Sources are added until 3,000 tokens are used. A chunk that doesn't fit is skipped and smaller ones after it still go in, so one long page doesn't end the list early. Repeats (the same chunk found by two rewrites) appear once.
3. **The rules** (`SYSTEM_PROMPT`). Use only what the sources state; end every factual sentence with its citations; don't do arithmetic, write it as an expression; if the sources fall short, set `answerable` to false and name the missing facts with their line items and periods (that note becomes the [retry's](corrective-rag.md) search); when asked for a judgement ("is the margin healthy?"), give it with the figures it rests on; at most four sentences, with units and fiscal periods.
4. **One JSON object** (JSON mode at temperature 0):

   ```json
   {"answerable": true,
    "answer": "Capital expenditure was $1,577 million in fiscal 2018 [3], or {c1}% of net sales [3][5].",
    "calculations": [{"id": "c1", "expression": "1,577 / 32,765 * 100", "decimals": 1}],
    "missing": ""}
   ```

   The reply is parsed leniently (code fences and prose around the object are ignored) and checked against a schema. A reply that still fails becomes an unanswerable answer with the error recorded, never an exception halfway through a run.
5. **The calculator** (`copilot.answer.calculator`). Each expression is cleaned (`1,577` becomes `1577`, currency signs go, `12.5%` becomes `(12.5 / 100)`) and then evaluated by the same safe parser the facts database uses for its formulas: the expression is parsed into a syntax tree, and only numbers, `+ - * /`, parentheses and signs are allowed. No names, no calls, no attributes, so a string a model wrote can't run code. The result, rounded to the decimals asked for, replaces `{c1}`: here "4.8". A failed expression shows as "[calculation failed]" and is counted.
6. **The citation check.** Citation numbers are read from the final text. Some models write citations in lenticular brackets, as "【2】" or "【2†L4-L9】", a habit from the browsing tools they were trained with; those are rewritten as "[2]" first. Numbers that match a source become the answer's cited sources; numbers that don't (a "[7]" when there are six sources) are recorded as invalid, and an answer with no valid citation at all is counted as uncited.

If the model says the sources fall short, the agent searches once more, more widely, before giving up: see [corrective RAG](corrective-rag.md).

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.answer.context.pack` | Numbered sources in rank order within the budget; `describe` writes the label |
| `copilot.answer.generate.generate` | The answer call: prompt, strong model, JSON mode |
| `parse_draft`, `build_answer` | Parse and validate the reply, run the calculations, fill the placeholders, check the citations |
| `copilot.answer.calculator` | `clean`, `calculate` and `run`: expressions in, formatted numbers out |
| `copilot.answer.agent.DocAgent` | Retrieve, build the context, answer, and retry once |
| `scripts/eval_context.py` | `poe eval-context`: how often an evidence page makes the context, by budget |
| `scripts/answer_questions.py` | `poe answer-questions`: answers dev questions, resumably, and scores them |

## How we measured it

**Context.** Before any answer is written, one question decides how good it can be: is an evidence page among the sources? On the 100 dev questions, with the retrieval of [ADR-0012](../decisions/0012-query-understanding-and-rewriting.md):

| Budget (tokens) | Sources (mean) | Evidence page in context | Against 3,000 (Holm-adjusted) |
|---|---|---|---|
| 1,500 | 4.2 | 0.52 | −0.16, p = 0.0006 |
| **3,000** | **8.2** | **0.68** | |
| 4,500 | 11.8 | 0.73 | +0.05, p = 0.064 |
| 3,000, split pages completed | 9.2 | 0.61 | −0.07, p = 0.030 |

3,000 tokens is the choice: halving it loses a sixth of the evidence, and 4,500 would cost every answer half as much again for a gain that isn't significant. Completing split pages (adding the other part of a long page next to a hit) spends the budget on text next to a hit rather than on the next-ranked hit, which more often holds the evidence. By question type, the evidence is in context for 0.91 of metrics-generated questions, which need statement pages that search finds easily, and for 0.59 and 0.55 of domain-relevant and novel-generated ones, which need narrative pages.

**Answers.** `poe answer-questions` records, for each question, whether it was answered, whether the retry ran, whether an evidence page was in the context and among the cited sources, invalid citations, failed calculations, tokens and latency. Whether the answers are *right* needs a judge ([LLM as judge](llm-as-judge.md)). On the 100 dev questions ([report](../eval/doc-agent-dev.md)):

- 65% of answers are correct by the default judge (0.56 to 0.74), 88% of the metrics-generated questions, and 6% are refusals.
- **Faithfulness**, a second judge call per answer (`copilot.eval.faithfulness`): every sentence of an answer is checked against the pages it cites, with the calculations behind its computed figures. 63% of answers are supported sentence by sentence by one judge and 68% by the other; 93% and 84% of citations contribute to the sentence they are attached to. Judgement sentences fare worst: 41% of domain-relevant answers are faithful, 87% of metrics-generated ones.
- 3% of answers carry no valid citation; none cites a source number that doesn't exist.

## Pitfalls we hit

- **The percent sign.** "12%" first became "1(2 / 100)": the pattern matched only the digit right before the sign. A lookbehind now takes the whole number.
- **Thousands separators.** A comma is removed only between a digit and exactly three more digits, so "1,577" becomes 1577 while "1,5" stays and fails loudly instead of silently becoming 15.
- **Citations the parser didn't see.** In the first smoke run, three of eight answers had no recognised citation: one cited in lenticular brackets, and two cited nothing although the prompt asked for it. The parser now reads both bracket styles, and the second prompt says that an answer without citations is not accepted and repeats the rule in the description of the JSON fields.
- **Tokens a minute.** An answer call uses about 4,000 tokens, and the free tier allows 8,000 a minute. A fixed three-second pause between calls ran into the limit on almost every call, so the pacer now waits for as long as the limit takes to earn back the tokens the last call used.
- **Split pages.** Completing them looked like a free improvement and lowered how often the evidence made the context (above).
- **Models build on their own calculations.** The answer model writes `c2 = c1 / 4756`, and the calculator first rejected the name: 11 of the dev run's calculations failed that way. Calculations now run in order, with earlier results substituted for their ids.
- **Placeholders with arithmetic and format codes.** The model also writes `{c1*100}` and `{c1*100:.1f}`, Python habits that left three answers showing a raw placeholder. The placeholder now takes one operation and a number of decimals. Both fixes change only what happens after the reply, so the whole dev run was rebuilt from the model-call cache with no new calls: failed calculations 11 to 0, unfilled placeholders 3 to 0, correctness unchanged.

## Review questions

1. Why does the model write expressions instead of computing the numbers itself?
2. The evidence is in context for 0.73 of questions at 4,500 tokens and 0.68 at 3,000. Why use 3,000?
3. FinanceBench marks one evidence page per fact. Why does that make "an evidence page is among the cited sources" a lower bound on citation quality?
4. What stops a calculation the model wrote from running arbitrary code?
5. Why do labels count PDF pages from one when the index counts from zero?

## References

- Gao et al., [Enabling Large Language Models to Generate Text with Citations](https://arxiv.org/abs/2305.14627) (ALCE), 2023: citation quality measured as recall and precision of the cited passages.
- Gao et al., [PAL: Program-aided Language Models](https://arxiv.org/abs/2211.10435), 2022: the model writes the program, an interpreter computes the answer.
- Liu et al., [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172), 2023: why more context isn't free.
- Python documentation, [`ast` — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html).
