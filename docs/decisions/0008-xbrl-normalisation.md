# ADR-0008: Normalise XBRL company facts into annual values as first reported

- **Status:** Accepted
- **Date:** 2026-10-17
- **Phase:** 1

## Context

The data agent (Phase 4) answers questions such as "What was 3M's capital expenditure in FY2018?" with SQL. SEC's company-facts API gives every XBRL fact a company has filed, but not in a shape SQL can use directly:

- a value appears once for every filing that reports it, because each 10-K repeats two or three years, and later filings may restate it;
- the `fy` on a fact is the fiscal year of the filing, not of the fact, and it is sometimes wrong (Best Buy's FY2021 10-K says 2020);
- companies tag the same line item differently, and change tags over time (revenue moved from `SalesRevenueNet` to `RevenueFromContractWithCustomerExcludingAssessedTax` after the 2018 accounting change);
- fiscal years end in different months, some run 52 or 53 weeks, and companies name them differently (Walmart's year ending January 2023 is fiscal 2023; Ulta's is fiscal 2022).

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Raw facts only, and let the SQL agent cope | No modelling work | Every query must deduplicate, pick tags and work out fiscal years; error-prone and slow |
| SEC's frames API (one value per calendar period) | Deduplicated by SEC | Calendar periods, not fiscal years; the value kept is the latest, so restated and split-adjusted |
| **Raw facts plus a curated `annual_values` table built by explicit rules** | Simple SQL for common questions; the raw facts remain for everything else; every rule is testable | Rules need maintaining as new cases appear |
| A third-party fundamentals dataset | Cleaned already | Licensing and cost; less transparent; not reproducible from public sources |

## Decision

Keep every fact from every 10-K, 10-K/A, 10-KT and 10-Q in a `facts` table, and build `annual_values` (one value per company, canonical metric and fiscal year) with these rules:

1. **Period end.** A filing's period end is the most common end date, within two weeks of the latest, among its `us-gaap` facts that cover a full fiscal year (10-K), quarter (10-Q) or transition period (10-KT) and end on or before the filing date.
2. **Fiscal-year label.** A 10-K's label comes from its period end, named the company's way: either by the year the fiscal year ends in, or by the year most of its days fall in. For each company, the way that agrees with more of SEC's labels wins.
3. **Current period only.** An annual value comes from facts in that fiscal year's own 10-K that end on its period end, so comparatives in later filings are never used.
4. **Full years only.** Duration metrics need a period of 350 to 380 days, which covers 52/53-week years and leaves out short transition years.
5. **Ranked tags.** Each of the 28 canonical metrics lists its tags in priority order; each year uses the highest-ranked tag reported that year.
6. **As first reported.** The value is the one in the original 10-K. The latest figure for the same period is stored beside it as `latest_value`.

## Evidence

- All 33 metrics questions in the FinanceBench dev split were rewritten as formulas over `annual_values`: single figures, ratios, growth rates, three-year averages and the cash conversion cycle. **All 33 match the gold answers exactly** at the precision each question asks for ([report](../../eval/results/facts/financebench-dev-checks.md)).
- Each period rule fixed a case found in real filings: comparatives outnumbering current-year facts (Nike's FY2010 balance sheet had been dated 2009), a forward-looking fact (Boeing's FY2017 10-K includes one ending December 2018), a stray context a day off (Foot Locker's FY2013 10-K), an 11-month transition year (Best Buy, 2013) and wrong SEC labels (Best Buy, Ulta, Foot Locker, Salesforce). After the rules, every company has one 10-K per fiscal year with no gaps, except a harmless duplicate accession at Salesforce, and no period ends after its filing date.

## Consequences

- Most numeric questions become one join between `annual_values` and `companies`.
- First-reported values match the documents FinanceBench asks about, including per-share figures before later stock splits. They also keep the filer's original tagging errors: MGM's FY2011 10-K tagged net income as −$30.3 million, corrected to $3,114.6 million a year later. `latest_value` exposes both cases; 1,523 of 15,359 values (10%) differ from their latest figure.
- Quarterly values, and the fourth quarter derived from annual minus year-to-date figures, are left to Phase 4's fiscal-calendar step (4.3).
- New tagging patterns will need new tags in the priority lists. The FinanceBench cross-check is the regression test for that: `uv run poe check-facts`.

## References

- SEC, [EDGAR application programming interfaces](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) (company facts, frames, submissions).
- FASB, US GAAP Financial Reporting Taxonomy (`us-gaap`).
- Islam et al., *FinanceBench* (2023), for the questions used as the cross-check.
