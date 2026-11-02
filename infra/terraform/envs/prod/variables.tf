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

variable "alert_email" {
  description = "Where alerts go. Kept out of the repository: pass it as TF_VAR_alert_email."
  type        = string
  sensitive   = true
}

variable "paid_daily_usd" {
  description = "The most the API may spend in a day on Cerebras when Groq refuses a call (ADR-0033); 0 turns the fallback off. Above 0, the key's secret must have a version."
  type        = number
  default     = 0.5
}

variable "sql_tier" {
  description = "Cloud SQL machine type: shared-core, Enterprise edition (ADR-0031)."
  type        = string
  default     = "db-f1-micro"
}

variable "sql_stop_schedule" {
  description = "When Cloud Scheduler stops the database every day (cron, Asia/Kolkata)."
  type        = string
  default     = "30 23 * * *"
}

variable "keep_alive_schedule" {
  description = "When Cloud Scheduler calls the API's readiness check, which reads from Qdrant (cron, Asia/Kolkata)."
  type        = string
  default     = "0 9 * * 1"
}
