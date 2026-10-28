# Project-level foundations, applied by hand by the project owner (see the deploy
# runbook). The project, its billing link, the budget and the state bucket are created
# first with gcloud, the budget before anything else, and imported here (imports.tf).

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  services = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])
}

resource "google_project_service" "this" {
  for_each = local.services

  service            = each.value
  disable_on_destroy = false
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account
  display_name    = "filings-research-copilot monthly"

  budget_filter {
    projects               = ["projects/${data.google_project.this.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.9
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }
}

resource "google_storage_bucket" "tfstate" {
  name                        = "${var.project_id}-tfstate"
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

# The data bundle the API image is built with (facts.db, the corpus filings' pages, the
# embedding models; ADR-0031), named by its checksum. CI reads it; nothing else does.
resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-data"
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.this]
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "images"
  format        = "DOCKER"
  description   = "Container images for the copilot's services"

  # Every build is scanned with Trivy in CI; the registry's own scanning costs $0.26 an
  # image and runs once, on demand, in the security pass (ADR-0031).
  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }

  # Keep the three newest versions of each image; delete anything else after a week.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "604800s"
    }
  }

  depends_on = [google_project_service.this]
}

resource "google_secret_manager_secret" "this" {
  for_each = var.secrets

  secret_id = each.value
  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

# Where the billing export lands (step 8.9). The owner turns the export on in the
# console; a US multi-region dataset gets the previous month's costs as well.
resource "google_bigquery_dataset" "billing_export" {
  dataset_id    = "billing_export"
  location      = "US"
  friendly_name = "Cloud Billing export"
  description   = "Standard usage cost export of the billing account, for the cost measurements"

  depends_on = [google_project_service.this]
}
