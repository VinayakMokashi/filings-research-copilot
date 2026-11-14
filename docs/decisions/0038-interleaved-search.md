# ADR-0038: Compare two rankings on a search page by team-draft interleaving, and call the counts illustrative

- **Status:** Accepted
- **Date:** 2026-11-15
- **Phase:** 9

## Context

Step 9.4, a stretch built last (decision E of 10 November), asks for a search page that interleaves two retrievers and logs clicks.

Offline, hybrid search (dense and BM25 fused) didn't beat dense search on FinanceBench ([ADR-0011](0011-retrieval-baseline.md)), whose questions follow a few templates. A reader's own words are a different test: names, figures and phrases that a keyword match could find where an embedding blurs them. Online evaluation can ask readers.

The constraints:

- **Traffic is thin,** so whatever compares the two needs few interactions.
- **No model calls,** so the page costs nothing to use and needs no quota.
- **A reader's words** shouldn't be kept to learn which ranking they preferred.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| An A/B test: half the readers see one ranking | Simple | Needs many readers; differences between readers swamp differences between rankings |
| Balanced interleaving (Joachims, 2002) | One reader judges both | Biased when the two rankings agree on many results |
| **Team-draft interleaving** (Radlinski, Kurup and Joachims, 2008) | One reader judges both; each result has one team, so shared results don't bias the count; few interactions needed (Chapelle et al., 2012) | A click is a noisy sign of relevance |
| Rankers with the doc agent's rewrites | What the copilot does | Calls a model for each search; tests the copilot, not the rankers |

## Decision

1. **A "Search" page in the web UI.** A reader's words return filing passages with no model call, through `POST /v1/search`. Opening a passage's page is a click (`POST /v1/search/click`).
2. **The two rankings:**
   - `a`, dense search, the doc agent's first stage;
   - `b`, hybrid search, the dense ranking fused with BM25's (ADR-0011's runner-up).

   Both search the filings that the query's companies and years pick out, as the doc agent does.
3. **Team-draft interleaving of 8 results.** In each round the team with fewer picks places its best result not yet shown, and a coin breaks a tie. The reader doesn't see the teams.
4. **Clicks.** Opening a result's page credits the team that placed it, once a result. A search goes to the team with more clicks; equal clicks are a tie; no click, no verdict.
5. **What is kept,** in Firestore `interleaving/<search id>`: the teams in list order, the number of filings searched, how far the two rankings overlapped, and the clicks. Never the query.
6. **The report** (`poe interleaving-report`): searches, clicks and wins by team, and a two-sided sign test on the decided searches. At this traffic the counts are illustrative, and the report says so.

## Consequences

- **A search costs** two embeddings of the query and two Qdrant queries on the API, about a second of CPU, plus Firestore writes, all within free tiers. It counts against no quota, since no model is called.
- **Searches in memory.** The newest 256 are held, so a click must come before the API's instance stops; the UI sends it as the page is opened.
- **A click is not a judgement of relevance.** Readers open what looks promising, and the top of a list draws more clicks. Team-draft interleaving gives each team its fair share of the top places, so position bias doesn't favour either ranking, but the counts compare the rankings only as readers' clicks see them.
- **The page compares rankers, not the copilot:** it skips the doc agent's rewrites and its answer.

## References

- Joachims, [Optimizing Search Engines using Clickthrough Data](https://www.cs.cornell.edu/people/tj/publications/joachims_02c.pdf), KDD 2002.
- Radlinski, Kurup and Joachims, [How Does Clickthrough Data Reflect Retrieval Quality?](https://www.cs.cornell.edu/people/tj/publications/radlinski_etal_08b.pdf), CIKM 2008.
- Chapelle, Joachims, Radlinski and Yue, [Large-Scale Validation and Analysis of Interleaved Search Evaluation](https://dl.acm.org/doi/10.1145/2094072.2094078), ACM TOIS 2012.
- [ADR-0011](0011-retrieval-baseline.md), [ADR-0031](0031-google-cloud-topology.md) (one API instance, Firestore).
