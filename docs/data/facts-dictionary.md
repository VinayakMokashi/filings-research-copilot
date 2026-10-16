# Data dictionary: the facts database

`data/processed/facts.db` is a SQLite database built by `uv run poe build-facts` from the SEC company facts of the 40 companies ([data card](sec-company-facts.md), [ADR-0008](../decisions/0008-xbrl-normalisation.md)). The SQL agent reads the table descriptions in [`data/reference/facts_descriptions.json`](../../data/reference/facts_descriptions.json); this page is the human version.

Money is in dollars, not millions. Dates are ISO strings (`YYYY-MM-DD`).

## Tables

### `annual_values`: one metric, one company, one fiscal year

The table most questions need. Each value is the figure in that fiscal year's own 10-K, as first reported.

| Column | Type | Meaning |
|---|---|---|
| `cik` | integer | The company (join to `companies`) |
| `metric` | text | A canonical metric from `metrics`, such as `revenue` |
| `fiscal_year` | integer | The company's own label for the year (see below) |
| `period_start` | text | First day of the fiscal year; NULL for balance-sheet items |
| `period_end` | text | Last day of the fiscal year, or the balance-sheet date |
| `value` | real | The value as originally reported |
| `unit` | text | `USD`, `USD/shares` (EPS) or `shares` |
| `tag` | text | The XBRL tag the value came from |
| `accn`, `filed` | text | The 10-K it came from and its filing date |
| `latest_value`, `latest_accn` | real, text | The figure for the same period in the most recent filing; different when it was restated (1,523 of 15,359 values) |

**Fiscal-year labels follow the company.** Walmart's year ending 31 January 2024 is fiscal 2024; Ulta's year ending 3 February 2024 is fiscal 2023. Each company's convention is worked out from its own filings ([ADR-0008](../decisions/0008-xbrl-normalisation.md)).

### `companies`

| Column | Type | Meaning |
|---|---|---|
| `cik` | integer | SEC Central Index Key, the primary key |
| `ticker` | text | Current ticker; NULL for Activision Blizzard and Foot Locker, which no longer trade |
| `name` | text | The short name used in questions, such as `Coca-Cola` |
| `sec_name` | text | SEC's registered name, such as `COCA COLA CO` |
| `sector` | text | GICS sector |
| `fiscal_year_end` | text | Month and day of the latest fiscal year end (`MMDD`) |

### `metrics` and `metric_tags`

`metrics` defines the 28 canonical metrics; `metric_tags` lists the tags behind each, in priority order. A lower-priority tag is used only in years when no higher one is reported, which handles companies changing tags over time. Revenue (`pick = 'largest'` in `metrics`) instead takes the largest figure among its tags, because a total can't be smaller than a part the company also tags.

| Metric | Label | Kind | Unit | Statement | Tags, in priority order |
|---|---|---|---|---|---|
| `revenue` | Revenue | duration | USD | income statement | `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `SalesRevenueNet`, `SalesRevenueGoodsNet`, `RevenuesNetOfInterestExpense` |
| `cost_of_revenue` | Cost of revenue | duration | USD | income statement | `CostOfRevenue`, `CostOfGoodsAndServicesSold`, `CostOfGoodsSold`, `CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization`, `CostOfServices` |
| `gross_profit` | Gross profit | duration | USD | income statement | `GrossProfit` |
| `research_and_development` | Research and development | duration | USD | income statement | `ResearchAndDevelopmentExpense`, `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` |
| `selling_general_administrative` | Selling, general and administrative | duration | USD | income statement | `SellingGeneralAndAdministrativeExpense` |
| `operating_income` | Operating income | duration | USD | income statement | `OperatingIncomeLoss` |
| `interest_expense` | Interest expense | duration | USD | income statement | `InterestExpense`, `InterestExpenseNonoperating`, `InterestExpenseDebt` |
| `income_tax_expense` | Income tax expense | duration | USD | income statement | `IncomeTaxExpenseBenefit` |
| `net_income` | Net income | duration | USD | income statement | `NetIncomeLoss`, `NetIncomeLossAvailableToCommonStockholdersBasic`, `ProfitLoss` |
| `eps_basic` | Basic EPS | duration | USD/shares | income statement | `EarningsPerShareBasic`, `EarningsPerShareBasicAndDiluted` |
| `eps_diluted` | Diluted EPS | duration | USD/shares | income statement | `EarningsPerShareDiluted`, `EarningsPerShareBasicAndDiluted` |
| `diluted_shares` | Diluted shares | duration | shares | income statement | `WeightedAverageNumberOfDilutedSharesOutstanding` |
| `depreciation_and_amortization` | Depreciation and amortization | duration | USD | cash flow statement | `DepreciationDepletionAndAmortization`, `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `Depreciation` |
| `operating_cash_flow` | Cash from operations | duration | USD | cash flow statement | `NetCashProvidedByUsedInOperatingActivities`, `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` |
| `capital_expenditure` | Capital expenditure | duration | USD | cash flow statement | `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets`, `PaymentsForCapitalImprovements` |
| `dividends_paid` | Dividends paid | duration | USD | cash flow statement | `PaymentsOfDividends`, `PaymentsOfDividendsCommonStock` |
| `share_repurchases` | Share repurchases | duration | USD | cash flow statement | `PaymentsForRepurchaseOfCommonStock` |
| `cash_and_equivalents` | Cash and equivalents | instant | USD | balance sheet | `CashAndCashEquivalentsAtCarryingValue`, `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`, `Cash` |
| `accounts_receivable` | Accounts receivable | instant | USD | balance sheet | `AccountsReceivableNetCurrent`, `ReceivablesNetCurrent` |
| `inventory` | Inventory | instant | USD | balance sheet | `InventoryNet`, `InventoryFinishedGoodsNetOfReserves` |
| `current_assets` | Current assets | instant | USD | balance sheet | `AssetsCurrent` |
| `property_plant_equipment_net` | Net PP&E | instant | USD | balance sheet | `PropertyPlantAndEquipmentNet`, `PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization` |
| `total_assets` | Total assets | instant | USD | balance sheet | `Assets` |
| `accounts_payable` | Accounts payable | instant | USD | balance sheet | `AccountsPayableCurrent`, `AccountsPayableTradeCurrent` |
| `current_liabilities` | Current liabilities | instant | USD | balance sheet | `LiabilitiesCurrent` |
| `long_term_debt` | Long-term debt | instant | USD | balance sheet | `LongTermDebtNoncurrent`, `LongTermDebtAndCapitalLeaseObligations` |
| `total_liabilities` | Total liabilities | instant | USD | balance sheet | `Liabilities` |
| `stockholders_equity` | Shareholders' equity | instant | USD | balance sheet | `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |

### `facts`

Every fact from every 10-K, 10-K/A, 10-KT and 10-Q: 1.06 million rows. A figure appears once for each filing that reported it, so comparatives repeat.

| Column | Type | Meaning |
|---|---|---|
| `cik` | integer | The company |
| `taxonomy`, `tag` | text | The concept, usually in `us-gaap` |
| `unit` | text | Such as `USD`, `shares`, `USD/shares`, `pure` |
| `period_start` | text | NULL for balance-sheet instants |
| `period_end` | text | End of the period, or the instant |
| `value` | real | The reported value |
| `accn`, `form`, `filed` | text | The filing that reported it |
| `fiscal_year`, `fiscal_period` | integer, text | SEC's labels for the filing (not for the fact) |
| `frame` | text | SEC's calendar-period label, set on one fact per period |

### `filings`

One row per 10-K, 10-K/A, 10-KT or 10-Q: `accn`, `cik`, `form`, `filed`, `fiscal_year` (the company's own label for annual reports; SEC's for quarterly ones), `fiscal_period` (`FY`, `Q1`, `Q2`, `Q3`), `period_end` and `sec_fiscal_year`.

### `concepts`

The `label` and `description` of each of the 4,233 XBRL concepts the companies use, keyed by `taxonomy` and `tag`.

## Example queries

3M's capital expenditure, FY2016 to FY2018, in millions:

```sql
SELECT a.fiscal_year, a.value / 1e6 AS capex_musd
FROM annual_values AS a
JOIN companies AS c USING (cik)
WHERE c.name = '3M' AND a.metric = 'capital_expenditure' AND a.fiscal_year BETWEEN 2016 AND 2018
ORDER BY a.fiscal_year;
-- 2016 1420.0, 2017 1373.0, 2018 1577.0
```

Working-capital ratio for every company in FY2022:

```sql
SELECT c.name, ca.value / cl.value AS working_capital_ratio
FROM annual_values AS ca
JOIN annual_values AS cl
  ON cl.cik = ca.cik AND cl.fiscal_year = ca.fiscal_year AND cl.metric = 'current_liabilities'
JOIN companies AS c ON c.cik = ca.cik
WHERE ca.metric = 'current_assets' AND ca.fiscal_year = 2022
ORDER BY working_capital_ratio DESC;
```

Values that were restated later:

```sql
SELECT c.name, a.metric, a.fiscal_year, a.value, a.latest_value
FROM annual_values AS a JOIN companies AS c USING (cik)
WHERE a.value != a.latest_value
ORDER BY ABS(a.latest_value - a.value) / ABS(a.value) DESC
LIMIT 10;
```

## Not covered yet

- **Quarterly values.** Quarterly figures are in `facts`, but turning year-to-date figures into quarters, and deriving the fourth quarter, is Phase 4's fiscal-calendar work.
- **Segments.** SEC's company-facts API has no dimensional facts, so segment and geographic figures aren't available.
- **Short years.** A transition period (Best Buy's 11-month year to February 2013) has balance-sheet values but no annual income or cash-flow values, because they wouldn't compare with full years.
