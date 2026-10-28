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

variable "cerebras_fallback" {
  description = "Whether the API may fall back to Cerebras when Groq refuses (the owner's choice); its key secret must then have a version."
  type        = bool
  default     = false
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
