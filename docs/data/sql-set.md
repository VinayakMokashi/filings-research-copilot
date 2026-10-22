# Data card: SQL eval set

| | |
|---|---|
| **What it is** | 42 analyst questions over the [facts database](facts-dictionary.md): 32 with verified gold SQL and 10 that can't be answered from it |
| **Files** | [`eval/sql/source.jsonl`](../../eval/sql/source.jsonl) (written by hand), [`eval/sql/questions.jsonl`](../../eval/sql/questions.jsonl) (with gold rows and splits) and [`eval/sql/checksums.json`](../../eval/sql/checksums.json) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-17, against the facts database built the same day |
| **Used for** | Execution accuracy of the data agent (Phase 4), including whether it declines what it can't answer |

## What's in it

| Category | Questions | Example |
|---|---|---|
| Lookup | 10 | "What was Microsoft's revenue in fiscal 2022, in billions of dollars?" |
| Ranking | 5 | "For each sector, which company had the highest revenue in fiscal 2022?" |
| Ratio | 5 | "What was General Mills' free cash flow in fiscal 2020, in millions?" |
| Aggregate | 3 | "Which companies reported a net loss in fiscal 2020?" |
| Trend | 3 | "Which companies grew revenue in every fiscal year from 2018 to 2022?" |
| Provenance | 3 | "Which fiscal 2021 annual values were later revised by more than 5%?" |
| Comparison | 2 | "Which companies spent more on capital expenditure than they generated from operations in fiscal 2020?" |
| Growth | 1 | "By what percentage did Adobe's revenue grow from fiscal 2021 to fiscal 2022?" |
| Unanswerable | 10 | "How much revenue did Apple's iPhone business bring in during fiscal 2022?" |

By difficulty: 13 easy, 17 medium and 12 hard. The hard ones need window functions, self-joins across fiscal years, `HAVING` clauses or the provenance columns (`tag`, `latest_value`).

The unanswerable questions cover a company outside the universe (Tesla), segment and product figures (iPhone, Azure), market data (share price, dividend yield), people (a chief executive), ratings, years before XBRL (fiscal 2005), and forecasts.

## How it was built

1. **Questions and gold SQL by hand** in `source.jsonl`. Questions use the companies' own fiscal years, and notes explain definitions that matter: R&D means the `research_and_development` metric, which Amazon doesn't report (it reports technology and content costs).
2. **Each result checked by hand.** Every gold query was run, and its result compared with the companies' reported figures: Microsoft's fiscal 2022 revenue of $198.27 billion, 3M's fiscal 2018 capex of $1,577 million (also a FinanceBench answer), Verizon's 2021 diluted EPS of $5.32, and so on.
3. **`uv run poe build-sql-set`** runs every gold query, stores its rows in `questions.jsonl`, and assigns the split.

Checking the results paid off. A 127% net margin for General Mills exposed a revenue tagging problem in the facts database (General Mills tags a $2 billion `Revenues` figure beside $19 billion of sales), and the fix also corrected American Express ([build log](../BUILD_LOG.md)).

## Scoring

A predicted query is right when its rows match the gold rows under text2sql-analyst's rules: row order and column order don't matter, numbers are compared at two decimal places (rounded half up), numeric strings count as numbers, and extra columns are allowed as long as every gold column is there and the rows line up. Declining an unanswerable question is right; declining an answerable one is wrong. Predicted queries run on a read-only connection with a step limit, so they can't change the database or run forever.

## Split

30% of each category, rounded half up, chosen at random with a fixed seed: dev has 28 questions (21 answerable, 7 not) and test has 14 (11 answerable, 3 not). The test side is held out like the other sets, and both sides are checksummed.

## Baselines

| Run | Dev accuracy (95% interval) |
|---|---|
| Gold SQL, declining the unanswerable | 1.000, a check of the scorer |
| Decline everything | 0.250 (0.107 to 0.429) |
| The data agent, before value linking ([ADR-0015](../decisions/0015-reuse-text2sql-analyst.md)) | 0.607 (0.429 to 0.786) |

## Known issues

- **Tied to one build of the facts database.** The gold rows reflect the data as fetched on 2026-10-17. After a refresh, `uv run pytest -m integration` re-runs every gold query and reports any whose rows changed.
- **One author.** The questions, SQL and checks come from a single author, with no second review.
- **Small.** With 28 dev questions, a 95% interval on accuracy near 50% spans about ±19 points; read it together with error analysis.
