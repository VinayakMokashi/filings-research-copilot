# The budget and the state bucket exist before Terraform does (the deploy runbook, step
# 1), so the first apply adopts them. The billing account stays out of the repository.

import {
  to = google_billing_budget.monthly
  id = "billingAccounts/${var.billing_account}/budgets/ee5c02bc-b93d-43ee-be9b-88fee89ef1bc"
}

import {
  to = google_storage_bucket.tfstate
  id = "filings-research-copilot-tfstate"
}
