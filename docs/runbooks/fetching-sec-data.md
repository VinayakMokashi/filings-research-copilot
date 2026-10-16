# Fetching SEC data

How to match the companies to SEC filers and download their XBRL company facts.

## Before you start

- `SEC_USER_AGENT` in `.env`, in the form `"Your Name you@example.com"`. SEC rejects requests that don't name a contact.
- FinanceBench fetched (`uv run poe fetch-financebench`), because the company list comes from its document file.

## Fetch

```bash
uv run poe fetch-sec
```

This takes about a minute. It:

1. downloads SEC's company ticker list and matches each FinanceBench company to a CIK;
2. downloads each company's submissions record (SEC's name, fiscal year end) and company facts;
3. writes `data/reference/companies.csv` and `data/reference/sec_manifest.json`, and caches the raw JSON under `data/raw/sec/`.

Cached files are reused. To download everything again, for example to pick up new filings:

```bash
uv run poe fetch-sec --refresh
```

A refresh changes the manifest. Commit it together with anything rebuilt from the new data, and note it in the build log.

## Build and check the facts database

```bash
uv run poe build-facts    # data/processed/facts.db, about 20 seconds
uv run poe check-facts    # the 33 FinanceBench cross-checks
```

`build-facts` prints row counts and, for each metric, the share of company-years from FY2015 to FY2023 that have a value. `check-facts` writes `eval/results/facts/financebench-dev-checks.md` and `.json`; after a refresh or a change to the normalisation rules, every check should still agree. If one doesn't, its row names the tags it used or the value it couldn't find.

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `SEC requires a User-Agent with a contact` | `SEC_USER_AGENT` is missing or has no email. Set it in `.env`. |
| `No SEC match for <name>` | A FinanceBench name didn't match SEC's ticker list. Find the company's CIK on EDGAR and add it to `TICKER_OVERRIDES` (if it still trades) or `CIK_OVERRIDES` in `src/copilot/ingest/universe.py`. |
| `returned HTTP 403` | SEC blocked the request, usually because of a missing or generic User-Agent. Check `SEC_USER_AGENT`. |
| `facts.db doesn't exist` | Run `uv run poe build-facts` first. |
| `returned HTTP 429` after retries | Too many requests. The client already waits between requests and honours `Retry-After`; wait a few minutes and run again. Cached files are kept. |
