variable "project_id" {
  description = "The copilot's own Google Cloud project."
  type        = string
  default     = "filings-research-copilot"
}

variable "region" {
  description = "Region for every regional resource (ADR-0016)."
  type        = string
  default     = "asia-south1"
}

variable "billing_account" {
  description = "Billing account ID that pays for the project. Kept out of the repository: pass it as TF_VAR_billing_account."
  type        = string
  sensitive   = true
}

variable "monthly_budget_usd" {
  description = "Monthly budget for the project, measured before credits so the trial credit can't hide spending."
  type        = number
  default     = 15
}

variable "github_repository_id" {
  description = "Numeric ID of the GitHub repository allowed to deploy (stable across renames and transfers)."
  type        = string
  default     = "1421062366"
}

variable "github_owner_id" {
  description = "Numeric ID of the repository's owner on GitHub."
  type        = string
  default     = "88434571"
}

variable "secrets" {
  description = "Secret Manager secrets. Terraform creates them empty; values are added with gcloud, so they never enter the Terraform state."
  type        = set(string)
  default = [
    "groq-api-key",
    "cerebras-api-key",
    "langfuse-public-key",
    "langfuse-secret-key",
    "qdrant-url",
    "qdrant-read-api-key",
    "qdrant-write-api-key",
    "sec-user-agent",
    "facts-url",
    "sql-admin-password",
  ]
}
