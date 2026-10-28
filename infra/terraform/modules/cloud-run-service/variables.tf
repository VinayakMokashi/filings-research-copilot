variable "name" {
  description = "Cloud Run service name."
  type        = string
}

variable "region" {
  description = "Cloud Run region."
  type        = string
}

variable "service_account" {
  description = "Email of the service account the service runs as."
  type        = string
}

variable "env" {
  description = "Plain environment variables. Secrets come from Secret Manager, never from here."
  type        = map(string)
  default     = {}
}

variable "secret_env" {
  description = "Environment variables read from Secret Manager at start: variable name => secret ID."
  type        = map(string)
  default     = {}
}

variable "memory" {
  description = "Memory limit per instance."
  type        = string
  default     = "512Mi"
}

variable "cpu" {
  description = "CPU limit per instance."
  type        = string
  default     = "1"
}

variable "max_instances" {
  description = "Upper bound on instances, which caps the cost of a traffic spike."
  type        = number
  default     = 1
}

variable "concurrency" {
  description = "Requests one instance handles at once."
  type        = number
  default     = 80
}

variable "timeout_seconds" {
  description = "Request timeout; a streamed answer or a websocket stays open this long at most."
  type        = number
  default     = 300
}

variable "session_affinity" {
  description = "Send a client's requests to the same instance where possible (Streamlit's websocket)."
  type        = bool
  default     = false
}

variable "vpc" {
  description = "Direct VPC egress for private addresses, or null for none."
  type = object({
    network    = string
    subnetwork = string
  })
  default = null
}

variable "public" {
  description = "Whether anyone may call the service without signing in."
  type        = bool
  default     = false
}

variable "invokers" {
  description = "Principals allowed to call a private service, such as serviceAccount:ui-runtime@..."
  type        = list(string)
  default     = []
}

variable "audiences" {
  description = "Extra audiences a caller's ID token may name, such as the service's deterministic address."
  type        = list(string)
  default     = []
}

variable "deletion_protection" {
  description = "Refuse terraform destroy."
  type        = bool
  default     = true
}
