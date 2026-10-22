# ADR-0015: Reuse text2sql-analyst as a pinned dependency, improved upstream first

- **Status:** Accepted
- **Date:** 2026-10-23
- **Phase:** 4

## Context

Phase 4's data agent answers questions about reported figures with SQL over the facts database ([ADR-0008](0008-xbrl-normalisation.md)). [text2sql-analyst](https://github.com/VinayakMokashi/text2sql-analyst), an earlier project, already has a tested Text-to-SQL pipeline: table selection by a model, SQL generation with self-repair from the database's error, a three-layer read-only guard, and a written analysis of the result.

It was built as an application, though. Its required dependencies included Streamlit, Altair and ChromaDB, a second vector database used to index table descriptions; its pipeline imported ChromaDB whether or not the index was used; and it called models through its own OpenAI-compatible client, outside this project's gateway, cache and pacing.

## Options considered

| Question | Options |
|---|---|
| How to reuse it | Pin it as it is; improve it upstream, then pin; copy the modules in |
| Finding the tables | Its vector index of table descriptions; offer every table |
| Models | Its own provider client; an adapter to this project's gateway |

## Decision

1. **Improve upstream, then pin.** text2sql-analyst [PR #1](https://github.com/VinayakMokashi/text2sql-analyst/pull/1) (version 0.2.0):
   - ChromaDB moved to an `index` extra, and Streamlit and Altair to an `app` extra; ChromaDB is imported only when a collection is opened.
   - A `SchemaRetriever` protocol, and an `AllTablesRetriever` that offers every table.
   - `hints`, passed from `Pipeline.ask` to the table-selection, generation and repair prompts. Without hints every prompt is unchanged.

   This project pins the merged commit: `text2sql-analyst @ git+https://github.com/VinayakMokashi/text2sql-analyst@2b89c30`.
2. **Every table is offered.** The facts database has seven tables, so `AllTablesRetriever` replaces the vector index, with the hand-written descriptions in `data/reference/facts_descriptions.json`.
3. **Models through the gateway.** `copilot.sql.adapter.GatewayLLM` implements text2sql-analyst's one model method on top of the cached, paced gateway. Its "sql" role (writing and repairing SQL) maps to the strong model, and "helper" (choosing tables, writing the analysis) to the fast one. Its calls are cached in a file of their own, `data/cache/sql.jsonl`.
4. **Its guardrails, unchanged:**
   - one SELECT, checked by sqlglot, on a read-only connection;
   - an SQLite authorizer that allows only reads;
   - caps of 200 rows, 1 MB per value and 10 seconds;
   - at most two repairs.

## Evidence

The baseline, text2sql-analyst with the hand-written descriptions and no value linking, on the SQL set's 28 dev questions ([run](../../eval/results/sql/sql-agent-v1/dev/summary.md)):

| Run | Accuracy (95% interval) | Answerable (21) | Unanswerable (7) |
|---|---|---|---|
| Decline everything | 0.250 | 0 | 7 |
| **Data agent, v1** | **0.607 (0.43 to 0.79)** | 12 | 5 |

- Against declining everything: +0.357 (0.11 to 0.57), p = 0.015 (paired permutation test).
- No query needed a repair and none failed to run; about 2,300 tokens a question; model time 1.6 seconds at the median and 2.2 at the 95th percentile.
- Seven of the nine wrong answers to answerable questions guessed a metric name that doesn't exist (`cashAndCashEquivalents`, `netProfitMargin`, a `LIKE '%asset%'` that also matched current assets). The table selection never chose the 28-row `metrics` table, so the SQL step never saw the real names. One declined a ratio it could compute from two metrics, and one returned company ids instead of names. Both wrong declines went the other way: the agent queried a company (Tesla) and a year (fiscal 2005) the database doesn't hold, and returned nothing instead of declining. All of these are value linking, the next step.
- The improved version added eight packages to this project (pandas, rich, sqlglot and their small dependencies); ChromaDB, Streamlit and Altair aren't installed.
- text2sql-analyst's own suite (190 tests, four of them new for library use) passes on Python 3.11 and 3.12.

## Consequences

- A change to the pipeline goes upstream first, and this project then moves its pin: two repositories to keep in step, in exchange for one tested implementation.
- Knowledge specific to the facts database (company names, metric names, fiscal years) enters through hints and descriptions, not through a fork of the prompts.
- The executor's read-only guard relies on SQLite's authorizer. Serving the facts from Postgres in Phase 8 needs a read-only role and a Postgres executor, upstream.

## References

- text2sql-analyst's [README](https://github.com/VinayakMokashi/text2sql-analyst#readme), including its own evaluation.
- ADR-0008 for the facts database and its tables.
