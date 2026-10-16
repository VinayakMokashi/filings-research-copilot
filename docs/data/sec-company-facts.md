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

## Known issues

- **The data moves.** Companies keep filing, so a refresh changes the files. The manifest records exactly what was used.
- **Repeated values.** A value appears once for every filing that reports it: a 10-K shows two or three years, so each year's figure recurs in later filings, and restated figures differ from the originals. Normalisation must choose which report counts.
- **`fy` describes the filing.** The fiscal year on a fact is the year of the filing that reported it, so a 2021 figure shown as a comparative in the 2023 10-K carries `fy = 2023`.
- **No segments.** The API returns only facts without dimensions, which means consolidated totals. Segment and geographic breakdowns aren't here.
- **Fiscal calendars differ.** Fiscal years end in January (Walmart, Best Buy), May (Nike, FedEx), June (Microsoft), August (Costco) and so on, and some companies use 52/53-week years that end on a weekday (AMD, Intel, PepsiCo, Kraft Heinz, Johnson & Johnson). The submissions record gives only the latest fiscal year end.
- **Changed tickers.** Block's ticker is now XYZ (formerly SQ); CIKs don't change, so the universe keys on CIK.
