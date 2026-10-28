# The facts tables on PostgreSQL: the same answers

Phase 8, step 8.4. The SQL set and FinanceBench's 33 dev figure questions. No test split was opened: the replays answered dev questions only, and the query-by-query check reran queries already on record.

## Question

The deployment runs the data agent's queries on PostgreSQL (Cloud SQL) during demo windows, and on the SQLite file the agent was built on otherwise ([ADR-0031](../decisions/0031-google-cloud-topology.md)). The agent keeps its prompts, which describe SQLite and were evaluated on it. Does PostgreSQL give the same results, and the same answers?

## Setup

- **The database.** `poe load-facts-postgres` copies facts.db's seven tables into PostgreSQL 18.6 (the Compose Postgres): 1,081,999 rows in 64 seconds on this laptop. The schema is the same, with keys, foreign keys and checks; REAL becomes DOUBLE PRECISION, because PostgreSQL's REAL has only four bytes. The database uses the C collation, so text sorts in SQLite's byte order. Queries run as `facts_reader`, a role with SELECT only, read-only transactions and a 15-second statement timeout (`copilot.facts.postgres`).
- **The translation.** The model still writes SQLite SQL. text2sql-analyst 0.4, improved upstream for this step (its PRs [#3](https://github.com/VinayakMokashi/text2sql-analyst/pull/3) and [#4](https://github.com/VinayakMokashi/text2sql-analyst/pull/4), pinned at `d5420f1`), translates each query with sqlglot, adds rules of its own, and returns SQLite's column names:

  | In SQLite | On PostgreSQL |
  |---|---|
  | `LIKE` ignores ASCII case | `ILIKE` |
  | `REAL` is an 8-byte float | `DOUBLE PRECISION` |
  | `ROUND(x, 2)` rounds a float | `ROUND(CAST(x AS NUMERIC), 2)` |
  | A comparison counts as 0 or 1 in `SUM` and `AVG` | cast to `INT` |
  | `TOTAL(x)` never returns NULL | `CAST(COALESCE(SUM(x), 0) AS DOUBLE PRECISION)` |
  | `WHERE` and `HAVING` may name a column alias | the alias's expression, where the name is no column |
  | An alias keeps its case; an expression is named by its text | the result's columns renamed to match |

  sqlglot itself keeps NULLs sorting first and division by zero returning NULL.
- **The SQLite check.** `FactsExecutor` compiles each query on facts.db with `EXPLAIN`, which runs nothing, before the server runs it (see the third finding below).
- **Query by query.** `poe check-facts-postgres` runs 119 distinct queries on both databases and compares columns and rows, floats bit for bit. The queries are:
  - the SQL set's 32 gold queries;
  - every query the data agent wrote in the SQL set's runs (`sql-agent-v1` and `sql-agent-v2`; dev and test traces already on record);
  - the queries it wrote for FinanceBench's dev figure questions (`data-agent-v1` and a smoke run, read from the git-ignored local answers).
- **End to end.** With `FRC_FACTS_URL` set, the data agent answered the SQL set's dev split and FinanceBench's 33 dev figure questions again, as runs `sql-agent-v2-postgres` and `data-agent-v1-postgres`. It used the same models as on record (Groq's gpt-oss-120b and Qwen3.8 27B). A model call whose prompt is unchanged replays from the cache.

## Results

### Query by query

| Outcome | Distinct queries | Uses |
|---|---|---|
| Identical, bit for bit | 116 | 119 |
| The same rows in another order | 3 | 3 |
| Different, or an error on one side only | 0 | 0 |

- Every gold query is identical, and so is every query from the FinanceBench runs (36 uses).
- The three order-only cases leave the order open. Two sort by a percentage rounded to two places, where rows tie (s29, in both agent versions); one has no `ORDER BY` at all (s27, from the test trace). SQL doesn't define the order of ties, and the two engines break them differently.
- A query took 6.3 ms at the median on SQLite and 12.9 ms on PostgreSQL. The PostgreSQL time includes the translation but not the connection; the server ran in Docker on the same laptop. Either is small next to the data agent's model calls (2.8 s at the median).

### End to end

| | SQLite (on record) | PostgreSQL |
|---|---|---|
| SQL set dev, execution accuracy | 1.000 (exact 95% interval 0.88 to 1.00) | 1.000 |
| SQL set dev, responses identical (status, SQL, attempts, errors, tables, tokens) | | 28 of 28 |
| FinanceBench dev figure questions, answers identical (text, SQL, rows, columns, statistics, chart) | | 33 of 33, all run on PostgreSQL |
| New model calls | | none: every call replayed from the cache |

The answers to the FinanceBench questions are identical, so their judgements are too: 32 of 33 correct ([report](data-agent-financebench.md)).

### Three differences, found and fixed on the way

The first query-by-query run used text2sql-analyst's first PostgreSQL release (#3), and 113 of the 119 queries matched. The first end-to-end replay then found a third difference.

1. **Column names.** PostgreSQL folds an alias to lower case (`AS roA` came back as `roa`) and names an expression after its function (`round`). Column names reach the charts and the analysis prompt. Upstream #4 renames the result's columns to what SQLite calls them.
2. **An alias in HAVING.** `HAVING net_income IS NOT NULL`, where `net_income` is a column alias of the same SELECT (s24), runs in SQLite. PostgreSQL answered that the column doesn't exist. Upstream #4 replaces such a reference with the alias's expression, but only where the name is not a column of the database.
3. **A query SQLite rejects.** In the first end-to-end replay, execution accuracy on the SQL set's dev split was 0.964 (27 of 28). For s16, the model's first query put a JOIN after WHERE. SQLite rejects that, and on SQLite the agent repaired it. sqlglot's more forgiving parser moved the JOIN into place, so PostgreSQL ran the first query and the agent kept it; the scorer, which runs SQL on SQLite, then rejected it. `FactsExecutor` now compiles every query on facts.db first, so PostgreSQL runs only what SQLite accepts, and a rejected query comes back with SQLite's own message.

## Decision

PostgreSQL gives the same answers. The deployment can run the data agent's queries on Cloud SQL in demo windows and on facts.db otherwise, with its prompts and their evaluations unchanged ([ADR-0031](../decisions/0031-google-cloud-topology.md)). The SQLite check stays: it is what makes the PostgreSQL path accept exactly the queries SQLite accepts.

## Logs

| What | Where |
|---|---|
| Query by query: the summary, and each use's outcome (ids only) | [`eval/results/facts/postgres-equivalence/`](../../eval/results/facts/postgres-equivalence/summary.json) |
| The SQL set's dev split on PostgreSQL | [`eval/results/sql/sql-agent-v2-postgres/dev/`](../../eval/results/sql/sql-agent-v2-postgres/dev/summary.md) |
| FinanceBench's figure questions on PostgreSQL (metrics; the answers stay in git-ignored `data/`) | [`eval/results/answers/data-agent-v1-postgres/dev/`](../../eval/results/answers/data-agent-v1-postgres/dev/summary.md) |
