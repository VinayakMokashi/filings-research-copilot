# Facts database against FinanceBench dev answers

33 of 33 checks agree. A check agrees when the computed value, rounded to the precision the question asks for, equals the gold answer.

| Question | Company | Formula | Gold | Computed | Agrees | Tags used or problem |
|---|---|---|---|---|---|---|
| 03029 | 3M | `capital_expenditure[2018] / 1e6` | 1577 | 1577 | yes | capital_expenditure: PaymentsToAcquirePropertyPlantAndEquipment |
| 04672 | 3M | `property_plant_equipment_net[2018] / 1e9` | 8.7 | 8.7 | yes | property_plant_equipment_net: PropertyPlantAndEquipmentNet |
| 02987 | Activision Blizzard | `revenue[2019] / ((property_plant_equipment_net[2018] + property_plant_equipment_net[2019]) / 2)` | 24.26 | 24.26 | yes | revenue: RevenueFromContractWithCustomerExcludingAssessedTax, property_plant_equipment_net: PropertyPlantAndEquipmentNet |
| 07966 | Activision Blizzard | `(capital_expenditure[2017] / revenue[2017] + capital_expenditure[2018] / revenue[2018] + capital_expenditure[2019] / revenue[2019]) / 3 * 100` | 1.9 | 1.9 | yes | capital_expenditure: PaymentsToAcquirePropertyPlantAndEquipment, revenue: Revenues, revenue: RevenueFromContractWithCustomerExcludingAssessedTax |
| 04735 | Adobe | `operating_cash_flow[2015] / current_liabilities[2015]` | 0.66 | 0.66 | yes | operating_cash_flow: NetCashProvidedByUsedInOperatingActivities, current_liabilities: LiabilitiesCurrent |
| 07507 | Adobe | `(operating_income[2016] / operating_income[2015] - 1) * 100` | 65.4 | 65.4 | yes | operating_income: OperatingIncomeLoss |
| 03856 | Adobe | `operating_cash_flow[2017] / current_liabilities[2017]` | 0.83 | 0.83 | yes | operating_cash_flow: NetCashProvidedByUsedInOperatingActivities, current_liabilities: LiabilitiesCurrent |
| 03882 | Amcor | `accounts_receivable[2020] / 1e6` | 1616 | 1616 | yes | accounts_receivable: AccountsReceivableNetCurrent |
| 05718 | American Water Works | `dividends_paid[2020] / 1e9` | 0.4 | 0.4 | yes | dividends_paid: PaymentsOfDividendsCommonStock |
| 04254 | American Water Works | `(operating_income[2021] + depreciation_and_amortization[2021]) / 1e6` | 1832 | 1832 | yes | operating_income: OperatingIncomeLoss, depreciation_and_amortization: DepreciationDepletionAndAmortization |
| 02608 | Best Buy | `(net_income[2015] / revenue[2015] + net_income[2016] / revenue[2016] + net_income[2017] / revenue[2017]) / 3 * 100` | 2.8 | 2.8 | yes | net_income: NetIncomeLoss, revenue: SalesRevenueNet |
| 04417 | Best Buy | `inventory[2019] / 1e6` | 5409 | 5409 | yes | inventory: InventoryNet |
| 04660 | Block | `current_assets[2016] / current_liabilities[2016]` | 1.73 | 1.73 | yes | current_assets: AssetsCurrent, current_liabilities: LiabilitiesCurrent |
| 03838 | Block | `(revenue[2020] / revenue[2019] - 1) * 100` | 101.5 | 101.5 | yes | revenue: Revenues |
| 07661 | Block | `operating_cash_flow[2020] / 1e6` | 382 | 382 | yes | operating_cash_flow: NetCashProvidedByUsedInOperatingActivities |
| 10285 | Boeing | `property_plant_equipment_net[2018] / 1e6` | 12645 | 12645 | yes | property_plant_equipment_net: PropertyPlantAndEquipmentNet |
| 03473 | Coca-Cola | `net_income[2017] / ((total_assets[2016] + total_assets[2017]) / 2)` | 0.01 | 0.01 | yes | net_income: NetIncomeLoss, total_assets: Assets |
| 09724 | Coca-Cola | `cost_of_revenue[2021] / revenue[2021] * 100` | 39.7 | 39.7 | yes | cost_of_revenue: CostOfGoodsAndServicesSold, revenue: Revenues |
| 06272 | Coca-Cola | `dividends_paid[2022] / net_income[2022]` | 0.80 | 0.80 | yes | dividends_paid: PaymentsOfDividends, net_income: NetIncomeLoss |
| 04209 | Costco | `total_assets[2021] / 1e6` | 59268 | 59268 | yes | total_assets: Assets |
| 05915 | CVS Health | `revenue[2018] / ((property_plant_equipment_net[2017] + property_plant_equipment_net[2018]) / 2)` | 17.98 | 17.98 | yes | revenue: Revenues, property_plant_equipment_net: PropertyPlantAndEquipmentNet |
| 04103 | General Mills | `365 * ((inventory[2018] + inventory[2019]) / 2) / cost_of_revenue[2019] + 365 * ((accounts_receivable[2018] + accounts_receivable[2019]) / 2) / revenue[2019] - 365 * ((accounts_payable[2018] + accounts_payable[2019]) / 2) / (cost_of_revenue[2019] + inventory[2019] - inventory[2018])` | -3.70 | -3.70 | yes | inventory: InventoryNet, cost_of_revenue: CostOfGoodsAndServicesSold, accounts_receivable: ReceivablesNetCurrent, revenue: RevenueFromContractWithCustomerExcludingAssessedTax, accounts_payable: AccountsPayableCurrent |
| 03471 | General Mills | `current_assets[2020] / current_liabilities[2020]` | 0.68 | 0.68 | yes | current_assets: AssetsCurrent, current_liabilities: LiabilitiesCurrent |
| 04854 | General Mills | `(operating_cash_flow[2020] - capital_expenditure[2020]) / 1e6` | 3215 | 3215 | yes | operating_cash_flow: NetCashProvidedByUsedInOperatingActivities, capital_expenditure: PaymentsToAcquirePropertyPlantAndEquipment |
| 10136 | General Mills | `1 - dividends_paid[2022] / net_income[2022]` | 0.54 | 0.54 | yes | dividends_paid: PaymentsOfDividends, net_income: NetIncomeLoss |
| 04171 | MGM Resorts | `accounts_payable[2018] / 1e6` | 303 | 303 | yes | accounts_payable: AccountsPayableCurrent |
| 03849 | MGM Resorts | `(capital_expenditure[2018] / revenue[2018] + capital_expenditure[2019] / revenue[2019] + capital_expenditure[2020] / revenue[2020]) / 3 * 100` | 7.9 | 7.9 | yes | capital_expenditure: PaymentsToAcquirePropertyPlantAndEquipment, revenue: RevenueFromContractWithCustomerExcludingAssessedTax |
| 04302 | Nike | `(cost_of_revenue[2016] / revenue[2016] + cost_of_revenue[2017] / revenue[2017] + cost_of_revenue[2018] / revenue[2018]) / 3 * 100` | 55.1 | 55.1 | yes | cost_of_revenue: CostOfGoodsSold, revenue: SalesRevenueNet |
| 03531 | Nike | `current_assets[2019] / 1e6` | 16525 | 16525 | yes | current_assets: AssetsCurrent |
| 04080 | Nike | `cost_of_revenue[2021] / ((inventory[2020] + inventory[2021]) / 2)` | 3.46 | 3.46 | yes | cost_of_revenue: CostOfGoodsAndServicesSold, inventory: InventoryFinishedGoodsNetOfReserves |
| 06247 | Walmart | `365 * ((accounts_payable[2017] + accounts_payable[2018]) / 2) / (cost_of_revenue[2018] + inventory[2018] - inventory[2017])` | 42.69 | 42.69 | yes | accounts_payable: AccountsPayableCurrent, cost_of_revenue: CostOfRevenue, inventory: InventoryNet |
| 04784 | Walmart | `(operating_income[2019] / revenue[2019] - operating_income[2018] / revenue[2018]) * 100` | 0.2 | 0.2 | yes | operating_income: OperatingIncomeLoss, revenue: Revenues |
| 06741 | Walmart | `((operating_income[2018] + depreciation_and_amortization[2018]) / revenue[2018] + (operating_income[2019] + depreciation_and_amortization[2019]) / revenue[2019] + (operating_income[2020] + depreciation_and_amortization[2020]) / revenue[2020]) / 3 * 100` | 6.2 | 6.2 | yes | operating_income: OperatingIncomeLoss, depreciation_and_amortization: DepreciationDepletionAndAmortization, revenue: Revenues, depreciation_and_amortization: DepreciationAmortizationAndAccretionNet |
