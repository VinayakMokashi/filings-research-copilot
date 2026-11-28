# To do

## Before 22 Dec 2026: cost guards for when the upgrade credit ends

The billing account is already paid (upgraded on 10 Nov 2026). Its upgrade credit runs to 22 Dec 2026; after that, usage beyond the free tier is billed to the card, so these guards keep the monthly cost bounded.

- [ ] Budget: set `monthly_budget_usd` to 10 in Terraform (a console edit is reverted by the next bootstrap apply), with alerts at 50%, 90% and 100% of spend and 100% of forecast.
- [ ] Hard cap: add a **Spend cap enforcement** budget for Cloud Run at $5 a month.
- [ ] Cerebras: decide whether to set `bandit_daily_usd = 0` and disable `canary.yml` (the bandit comparison ended 23 Nov), and lower `paid_daily_usd` to 0.15.
- [ ] Data bucket: its 90-day delete rule removes the deploy bundle uploaded on 2 Nov around 31 Jan 2027. Re-upload it or exempt it from the rule.

Estimated cost after the trial (28 Nov 2026 estimate, not a measurement): about $2.35 to $4.20 a month on Google Cloud, plus about $5 to $8.50 a month on Cerebras.
