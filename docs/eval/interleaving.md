# The interleaved search page: the first check

Phase 9, step 9.4 ([ADR-0038](../decisions/0038-interleaved-search.md), [guide](../concepts/online-evaluation.md#interleaving), [runbook](../runbooks/search-page.md)). The web UI's Search page went live on 15 November. This report keeps the live check and the method; the Phase 9 close adds readers' counts, which stay illustrative at this traffic.

## Question

When readers search the filings, which ranking do they prefer? The candidates are dense search alone (the doc agent's first stage) and hybrid search (dense and BM25 fused). Offline, on FinanceBench's templated questions, the two tied (ADR-0011).

## Setup

- **Team-draft interleaving** (Radlinski et al., 2008). The two rankings take turns placing their best result not yet shown, and when both have placed as many, a coin decides who goes next. Each of the 8 results remembers its ranking.
- **Clicks.** Opening a result's page credits its ranking, once a result. A search goes to the ranking with more clicks; one with no clicks, or as many for each, is a tie.
- **Kept:** in Firestore `interleaving/<search id>`, the teams in list order, how many filings were searched, the two rankings' overlap, and each click. Never the query.
- **Counted** by `poe interleaving-report`: wins by ranking, and a sign test on the searches one ranking won.

## The live check (15 November)

One search through the private API, with the owner's identity token, then three clicks:

- **The search** named one company, so it searched that company's three filings and returned 8 results that alternated the rankings, dense first.
  - The coin picked dense first in each of the four rounds, as a fair coin does once in 16. Production draws it afresh at each tie, from the system's entropy.
  - The two rankings shared 4 of their top 8 results.
- **The clicks:**
  - a click on the second result returned 204 and credited hybrid search;
  - the same click again returned 204 and wasn't counted twice;
  - a click on a search that doesn't exist returned 404.
- **Firestore** kept the teams, the overlap, the number of filings and the click (`clicks: 1`), and nothing of the query.
- **The check's document was deleted,** so readers' counts start from zero.

## Limits

- **Few readers.** A sign test needs dozens of decided searches to tell the rankings apart, and the live demo answered 3 questions in its first two weeks. The counts are illustrative.
- **A click isn't a judgment.** A reader opens what looks relevant from its snippet, so a click doesn't say the passage answered them. Results higher on the page also draw more clicks. Interleaving balances that between the rankings, since each places as many results near the top.
- **Searches are held in memory** for their clicks, as one API instance runs. A restart forgets them, and a click on a forgotten search is refused.
