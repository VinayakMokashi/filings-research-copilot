# Data cards

One card per dataset, written when the dataset is added (Phase 1 onwards).

Each card records:

- Source and URL
- Licence and allowed use
- Download date
- Size and checksum
- Fields used
- Splits, and how they were made
- Known issues

| Card | What it is | Added |
|---|---|---|
| [FinanceBench](financebench.md) | 150 questions over real filings, with answers and evidence pages; the evaluation benchmark | 2026-10-17 |
| [Routing set](routing-set.md) | 198 questions labelled with the route the copilot should take | 2026-10-17 |
| [SEC company facts](sec-company-facts.md) | XBRL financial facts and the company universe from SEC EDGAR | 2026-10-17 |
| [Facts database dictionary](facts-dictionary.md) | Every table and column in the SQLite facts database | 2026-10-17 |
| [SQL set](sql-set.md) | 42 questions over the facts database, with verified gold SQL or a reason to decline | 2026-10-17 |
| [Synthetic pairs](synthetic-pairs.md) | 1,006 LLM-written questions paired with the chunks that answer them, from training filings only, for fine-tuning in Phase 7 | 2026-10-18 |
| [Answer labels](answer-labels.md) | 41 correctness labels for the doc agent's dev answers, from a Claude model, for checking the answer judge | 2026-10-23 |
| [Hybrid set](hybrid-set.md) | 13 questions that need figures from the facts database and an explanation from the filing, for the hybrid-answer prototype | 2026-10-23 |
| [Memory set](memory-set.md) | 10 conversations from 6 users, for follow-up rewriting and the notes kept about users | 2026-10-23 |
