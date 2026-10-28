# Research briefs from a crew of agents

> Plan a brief as an analyst would, have the specialists write its sections from their own sources, check every sentence, and only then summarise.

**Lands in:** Phase 7 · **Code:** `src/copilot/agents/brief.py`, `src/copilot/eval/briefs.py`, `scripts/run_briefs.py`, `POST /v1/brief`

## What it is

A request for a brief ("Write a one-page brief on 3M's 2022 for an investment committee: results, segments, litigation and liquidity") asks for several things at once. One retrieval can't serve them all: the results are in the income statement, the segments in their own note, the litigation in Item 3 and the notes, the liquidity in the MD&A. A **crew** splits the work among agents, each with one job:

- a **planner**, which decides what the brief needs;
- **writers**, the copilot's existing specialists, each answering one section's question from its own sources;
- a **critic**, which checks what the writers wrote;
- an **editor**, which pulls the sections together.

**Self-Discover** (Zhou et al., 2024) is how the planner works. Instead of one fixed recipe, a model given a list of reasoning modules SELECTs the ones a task needs, ADAPTs each to the task, and IMPLEMENTs them as a structured plan to follow. Here the modules are the parts of an analyst's brief (results, segments, profitability, cash flow, liquidity and leverage, capital returns, risks, legal matters, outlook, strategy, one-off items), and the plan is two to five sections, each a standalone question for the doc agent or the hybrid.

## Why we need it here

Since Phase 5 the router has recognised requests for briefs, and until now it answered them with a note to ask about one part at a time. The specialists answer one question well; a brief needs several answered and put together, and the copilot's guarantees (every sentence cites a source, and a check reads it against that source) must hold for the whole of it.

## How it works

1. **Plan** (one call on the strong model): select the modules, adapt them, and write the sections, each with a heading, a question naming the company and the period, and its writer. A plan that can't be read falls back to one section, the request itself.
2. **Write**, in parallel threads: the doc agent answers what the filings' text says, the hybrid the figures and their reasons; each section has its own retrieval and its own cited sources. The hybrid's calls go one at a time, since its data agent shares one database connection.
3. **Check:** the validator's checker (the `small` role, a model that writes none of the sections and grades none of the evaluation) reads every sentence against the sources it cites; sentences it can't support are cut, and a section with nothing left is dropped and named as not covered.
4. **Edit:** the sections' sources are numbered once for the whole brief (a page cited by two sections keeps one number), and one call writes a summary from the sections' own sentences, citing the brief's numbers; the summary is checked and cut the same way.
5. **The brief** is Markdown: the title, the summary, and each section's heading and text, with its sources listed as an answer's are. `POST /v1/brief` streams the crew's steps (plan, each section, edit) as events, and the chat's "Write a brief" switch calls it.

## Where it lives in the code

| Piece | What it does |
|---|---|
| `copilot.agents.brief` | The modules, the plan and its fallback, the writers, the critic, the merged sources, the editor, the Markdown |
| `copilot.agents.graph` | The brief node runs the crew; a caller can ask for a route (`requested_route`) |
| `copilot.api.app` | `POST /v1/brief`, the brief route asked for, cached apart from answers |
| `copilot.eval.briefs` | The brief set, its rubrics and the rubric judge |
| `scripts/run_briefs.py` (`poe run-briefs`) | Writes the set's briefs with the crew or one specialist, resumably, and grades them |

## How we measured it

On the project's brief set, 12 requests with rubrics ([report](../eval/brief-crew.md)):

| Measure | Doc agent, one shot | Crew |
|---|---|---|
| Rubric items covered | 0.66 | 0.86 (+0.20, p = 0.18) |
| Sentences supported | 0.76 | 0.92 (+0.15, p = 0.22) |
| Requests answered | 10 of 12 | 12 of 12 |
| Distinct sources | 3.0 | 7.1 (p = 0.0008) |
| Length, cost, time | 97 words, $0.004, 40 s | 411 words, $0.015, 91 s |

The crew became the brief route ([ADR-0030](../decisions/0030-brief-crew.md)): it answers every request with briefs rather than answers, though 12 briefs can't make its lead on coverage significant. A second judge agrees with the first on 95% of the crew's rubric items.

## Pitfalls we hit

- **Two baselines that were one.** The hybrid sends a question about one company and one year to the doc agent alone (step 5.1), and every brief request is one, so the "hybrid, one shot" baseline turned out word for word the doc agent's. A baseline is only a second baseline if it takes a different path on these inputs.
- **Fully faithful favours short answers.** Every sentence was supported in 8 of the one shot's 12 briefs and in 4 of the crew's: a four-sentence answer has fewer chances to slip than a twenty-sentence brief. The share of sentences supported compares them fairly.
- **The critic can empty a section.** Cutting unsupported sentences without a revision left Coca-Cola's profitability section with nothing, and the brief names it as not covered.
- **Modules need an industry.** The liquidity module asks about cash, debt and credit facilities; for a bank the planner should have asked about capital ratios, and the section went unanswered.
- **The critic's quota.** The checker runs on Groq's free tier; the crew's 12 briefs nearly filled its daily 200,000 tokens, and the baselines waited hours for the rolling window to clear.

## Review questions

1. Why does a brief need a plan before any retrieval, when a single answer doesn't?
2. What does the critic's independence from the writers and from the evaluation's judge protect against?
3. Why number the sources once for the whole brief rather than keep each section's own numbers?
4. A rubric checks what a brief covers and the faithfulness check whether it is right. Why grade those apart?

## References

- Zhou et al., [Self-Discover: Large Language Models Self-Compose Reasoning Structures](https://arxiv.org/abs/2402.03620), 2024.
- Wu et al., [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155), 2023 (agents with roles).
- Kim et al., [Prometheus: Inducing Fine-grained Evaluation Capability in Language Models](https://arxiv.org/abs/2310.08491), 2023 (rubric-based grading).
