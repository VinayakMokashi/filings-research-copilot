"""Canonical metrics and their annual values (ADR-0008).

A canonical metric such as `capital_expenditure` maps to a ranked list of `us-gaap` tags,
because companies tag the same line item differently, and change tags over time. For each
company and fiscal year, the annual value is:

- taken from the 10-K for that fiscal year, using only its current-period facts (facts that
  end on the filing's period end), so comparatives from later filings are never used;
- for duration metrics, a period of 350 to 380 days, which covers 52/53-week years;
- from the highest-ranked tag that has such a value that year;
- the value as originally reported (the earliest filing), with the latest reported value for
  the same period kept alongside to show restatements.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from copilot.facts.normalise import ANNUAL_DAYS, ANNUAL_FORMS, Fact, Filing, duration_days

Kind = Literal["duration", "instant"]
Statement = Literal["income statement", "cash flow statement", "balance sheet"]


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    label: str
    description: str
    kind: Kind
    unit: str
    statement: Statement
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnnualValue:
    cik: int
    metric: str
    fiscal_year: int
    start: str | None
    end: str
    value: float
    unit: str
    tag: str
    accn: str
    filed: str
    latest_value: float
    latest_accn: str


def _m(
    name: str,
    label: str,
    description: str,
    statement: Statement,
    *tags: str,
    kind: Kind = "duration",
    unit: str = "USD",
) -> Metric:
    return Metric(name, label, description, kind, unit, statement, tags)


IS: Statement = "income statement"
CF: Statement = "cash flow statement"
BS: Statement = "balance sheet"

METRICS: tuple[Metric, ...] = (
    _m(
        "revenue",
        "Revenue",
        "Total revenue or net sales for the fiscal year.",
        IS,
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenuesNetOfInterestExpense",
    ),
    _m(
        "cost_of_revenue",
        "Cost of revenue",
        "Cost of goods and services sold (COGS).",
        IS,
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        "CostOfServices",
    ),
    _m(
        "gross_profit",
        "Gross profit",
        "Revenue minus cost of revenue, as reported.",
        IS,
        "GrossProfit",
    ),
    _m(
        "research_and_development",
        "Research and development",
        "Research and development expense.",
        IS,
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ),
    _m(
        "selling_general_administrative",
        "Selling, general and administrative",
        "Selling, general and administrative expense.",
        IS,
        "SellingGeneralAndAdministrativeExpense",
    ),
    _m(
        "operating_income",
        "Operating income",
        "Operating income (loss), unadjusted.",
        IS,
        "OperatingIncomeLoss",
    ),
    _m(
        "interest_expense",
        "Interest expense",
        "Interest expense.",
        IS,
        "InterestExpense",
        "InterestExpenseNonoperating",
        "InterestExpenseDebt",
    ),
    _m(
        "income_tax_expense",
        "Income tax expense",
        "Income tax expense (benefit).",
        IS,
        "IncomeTaxExpenseBenefit",
    ),
    _m(
        "net_income",
        "Net income",
        "Net income (loss) attributable to the parent company's shareholders.",
        IS,
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ),
    _m(
        "eps_basic",
        "Basic EPS",
        "Basic earnings per share.",
        IS,
        "EarningsPerShareBasic",
        "EarningsPerShareBasicAndDiluted",
        unit="USD/shares",
    ),
    _m(
        "eps_diluted",
        "Diluted EPS",
        "Diluted earnings per share.",
        IS,
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        unit="USD/shares",
    ),
    _m(
        "diluted_shares",
        "Diluted shares",
        "Weighted-average diluted shares outstanding.",
        IS,
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        unit="shares",
    ),
    _m(
        "depreciation_and_amortization",
        "Depreciation and amortization",
        "Depreciation and amortization, as added back in the cash flow statement.",
        CF,
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ),
    _m(
        "operating_cash_flow",
        "Cash from operations",
        "Net cash provided by (used in) operating activities.",
        CF,
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    _m(
        "capital_expenditure",
        "Capital expenditure",
        "Cash paid for property, plant and equipment (capex).",
        CF,
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
    ),
    _m(
        "dividends_paid",
        "Dividends paid",
        "Cash dividends paid to shareholders.",
        CF,
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
    ),
    _m(
        "share_repurchases",
        "Share repurchases",
        "Cash paid to repurchase common stock.",
        CF,
        "PaymentsForRepurchaseOfCommonStock",
    ),
    _m(
        "cash_and_equivalents",
        "Cash and equivalents",
        "Cash and cash equivalents at the end of the year.",
        BS,
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
        kind="instant",
    ),
    _m(
        "accounts_receivable",
        "Accounts receivable",
        "Accounts receivable, net, current.",
        BS,
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        kind="instant",
    ),
    _m(
        "inventory",
        "Inventory",
        "Inventories, net.",
        BS,
        "InventoryNet",
        "InventoryFinishedGoodsNetOfReserves",
        kind="instant",
    ),
    _m(
        "current_assets",
        "Current assets",
        "Total current assets.",
        BS,
        "AssetsCurrent",
        kind="instant",
    ),
    _m(
        "property_plant_equipment_net",
        "Net PP&E",
        "Property, plant and equipment, net of depreciation.",
        BS,
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
        kind="instant",
    ),
    _m("total_assets", "Total assets", "Total assets.", BS, "Assets", kind="instant"),
    _m(
        "accounts_payable",
        "Accounts payable",
        "Accounts payable, current.",
        BS,
        "AccountsPayableCurrent",
        "AccountsPayableTradeCurrent",
        kind="instant",
    ),
    _m(
        "current_liabilities",
        "Current liabilities",
        "Total current liabilities.",
        BS,
        "LiabilitiesCurrent",
        kind="instant",
    ),
    _m(
        "long_term_debt",
        "Long-term debt",
        "Long-term debt, excluding the current portion.",
        BS,
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        kind="instant",
    ),
    _m(
        "total_liabilities",
        "Total liabilities",
        "Total liabilities, where the company reports it.",
        BS,
        "Liabilities",
        kind="instant",
    ),
    _m(
        "stockholders_equity",
        "Shareholders' equity",
        "Total equity attributable to the parent company.",
        BS,
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        kind="instant",
    ),
)
METRICS_BY_NAME: dict[str, Metric] = {metric.name: metric for metric in METRICS}


def is_annual_period(start: str | None, end: str) -> bool:
    return duration_days(start, end) in ANNUAL_DAYS


def annual_values(
    facts: Iterable[Fact], filings: Mapping[str, Filing], metric: Metric
) -> list[AnnualValue]:
    """The metric's value for every fiscal year with a 10-K, following the module's rules."""
    rank = {tag: position for position, tag in enumerate(metric.tags)}
    by_period: dict[tuple[str, str | None, str], list[Fact]] = {}
    current: dict[int, list[Fact]] = {}
    for fact in facts:
        if fact.taxonomy != "us-gaap" or fact.tag not in rank or fact.unit != metric.unit:
            continue
        if fact.form not in ANNUAL_FORMS:
            continue
        if metric.kind == "duration" and not is_annual_period(fact.start, fact.end):
            continue
        if metric.kind == "instant" and fact.start is not None:
            continue
        by_period.setdefault((fact.tag, fact.start, fact.end), []).append(fact)
        filing = filings[fact.accn]
        if fact.end == filing.period_end and filing.fiscal_year is not None:
            current.setdefault(filing.fiscal_year, []).append(fact)

    values = []
    for fiscal_year, candidates in sorted(current.items()):
        best_tag = min((fact.tag for fact in candidates), key=rank.__getitem__)
        reports = sorted(
            (f for f in candidates if f.tag == best_tag), key=lambda f: (f.filed, f.accn)
        )
        original = reports[0]
        history = sorted(
            by_period[(original.tag, original.start, original.end)], key=lambda f: (f.filed, f.accn)
        )
        latest = history[-1]
        values.append(
            AnnualValue(
                cik=original.cik,
                metric=metric.name,
                fiscal_year=fiscal_year,
                start=original.start,
                end=original.end,
                value=original.value,
                unit=metric.unit,
                tag=original.tag,
                accn=original.accn,
                filed=original.filed,
                latest_value=latest.value,
                latest_accn=latest.accn,
            )
        )
    return values
