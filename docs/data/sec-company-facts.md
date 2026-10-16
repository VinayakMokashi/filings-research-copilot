# Data card: SEC company facts

| | |
|---|---|
| **Source** | SEC EDGAR: the [company ticker list](https://www.sec.gov/files/company_tickers.json), [submissions](https://data.sec.gov/submissions/CIK0000066740.json) and [XBRL company facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000066740.json) APIs |
| **Licence and use** | Public data published by the SEC. Access follows SEC's fair-access policy: every request declares a contact in its User-Agent, and the client stays at 5 requests per second, under SEC's limit of 10. |
| **Downloaded** | 2026-10-17 (the exact time of each file is in the manifest) |
| **Fetch** | `uv run poe fetch-sec` ([runbook](../runbooks/fetching-sec-data.md)) |
| **Committed** | [`data/reference/companies.csv`](../../data/reference/companies.csv) (the universe) and [`data/reference/sec_manifest.json`](../../data/reference/sec_manifest.json) (every file's URL, time, size and SHA-256). The raw JSON (175 MB) stays in `data/raw/sec/`. |

## The universe

The universe is every company in FinanceBench's document list: the 32 companies its questions ask about, plus 8 with filings but no questions (Apple, eBay, FedEx, Intel, McDonald's, Oracle, PG&E and Salesforce). Each company is matched to its SEC Central Index Key (CIK):

| How it was matched | Companies |
|---|---|
| Name, after normalising case, punctuation, "&" and suffixes such as Inc., Corp. or plc | 32 |
| Ticker override, where the names differ too much ("JPMorgan" is "JPMORGAN CHASE & CO") | 6: AMD, Amazon, Costco, JPMorgan, MGM Resorts, Verizon |
| CIK override, for companies that no longer trade and so aren't in the ticker list | 2: Activision Blizzard (CIK 718877) and Foot Locker (CIK 850209) |

Every match was then checked against the company's submissions record, which gives SEC's name for it and its fiscal year end.

## What's in it

For each company, the company-facts file holds every XBRL fact it has filed, grouped by taxonomy (`us-gaap`, `dei`, and a few others), concept and unit. Each fact records:

| Field | Meaning |
|---|---|
| `start`, `end` | The period: a duration (both dates) or an instant (`end` only, for balance-sheet items) |
| `val` | The value, in the unit it is grouped under (`USD`, `shares`, `USD/shares`, `pure`) |
| `accn` | The accession number of the filing that reported it |
| `form`, `filed` | The form type (10-K, 10-Q, 8-K, ...) and the filing date |
| `fy`, `fp` | The fiscal year and period of the filing, not of the fact |
| `frame` | SEC's calendar-period label (such as `CY2021`), set on one fact per period |

3M's file, for example, has 35,334 facts across 700 `us-gaap` concepts. The largest file is JPMorgan's (8.0 MB); all 40 together are 164 MB, and the submissions files add 11 MB.

## From raw facts to the facts database

`uv run poe build-facts` turns the 40 files into `data/processed/facts.db` (257 MB, not committed) in about 20 seconds: 1.06 million facts from 2,623 filings, 4,233 concepts, and 15,359 annual values for 28 canonical metrics. The rules are in [ADR-0008](../decisions/0008-xbrl-normalisation.md), the guide is [xbrl-and-financial-metrics.md](../concepts/xbrl-and-financial-metrics.md), and every table and column is in the [data dictionary](facts-dictionary.md).

**Cross-check.** `uv run poe check-facts` rewrites each of the 33 metrics questions in the FinanceBench dev split as a formula over the annual values. All 33 match the gold answers exactly at the precision the question asks for ([report](../../eval/results/facts/financebench-dev-checks.md)).

**Spot check.** `uv run poe spot-check-facts` draws 20 random annual values with links to their filings, for checking by hand ([sheet](facts-spot-check.md)).

## Known issues

- **The data moves.** Companies keep filing, so a refresh changes the files. The manifest records exactly what was used.
- **Repeated values.** A value appears once for every filing that reports it: a 10-K shows two or three years, so each year's figure recurs in later filings, and restated figures differ from the originals. Normalisation must choose which report counts.
- **`fy` describes the filing.** The fiscal year on a fact is the year of the filing that reported it, so a 2021 figure shown as a comparative in the 2023 10-K carries `fy = 2023`.
- **No segments.** The API returns only facts without dimensions, which means consolidated totals. Segment and geographic breakdowns aren't here.
- **Fiscal calendars differ.** Fiscal years end in January (Walmart, Best Buy), May (Nike, FedEx), June (Microsoft), August (Costco) and so on, and some companies use 52/53-week years that end on a weekday (AMD, Intel, PepsiCo, Kraft Heinz, Johnson & Johnson). The submissions record gives only the latest fiscal year end.
- **Changed tickers.** Block's ticker is now XYZ (formerly SQ); CIKs don't change, so the universe keys on CIK.
- **SEC's fiscal-year labels are sometimes wrong.** Best Buy's FY2021 10-K is labelled 2020, and Ulta, Foot Locker and Salesforce have similar slips. The database derives each 10-K's label from its period end instead.
- **Original filings contain tagging errors.** MGM's FY2011 10-K tagged net income as −$30.3 million; the next year's filing corrected it to $3,114.6 million. Stock splits also restate share counts (Amazon, 2022). The database keeps the first-reported value and the latest one side by side.
- **Transition years.** Best Buy's 2013 transition report covers 11 months, so that year has balance-sheet values but no annual flow values.
