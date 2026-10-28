terraform {
  required_version = ">= 1.10"

  backend "gcs" {
    bucket = "filings-research-copilot-tfstate"
    prefix = "envs/prod"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  sa = {
    for name in ["api", "ui", "mcp", "worker", "scheduler", "pubsub"] :
    name => "${name}-runtime@${var.project_id}.iam.gserviceaccount.com"
  }
  # Cloud Run's deterministic address for a service, known before it exists.
  host = { for name in ["api", "ui", "mcp", "worker"] : name => "${name}-${data.google_project.this.number}.${var.region}.run.app" }
}
