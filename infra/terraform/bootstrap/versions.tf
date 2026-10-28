terraform {
  required_version = ">= 1.10"

  backend "gcs" {
    bucket = "filings-research-copilot-tfstate"
    prefix = "bootstrap"
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

  # Bill API quota (budgets, IAM) to this project rather than to the caller's default.
  billing_project       = var.project_id
  user_project_override = true
}
