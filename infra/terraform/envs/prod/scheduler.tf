# Two scheduled calls (ADR-0031), both signed as the scheduler's own account:
# - every week, the API's readiness check, which also reads from Qdrant, so the free
#   cluster is never idle for a week (it would be suspended);
# - every night, the Cloud SQL Admin API stops the database, whatever demo-down did.

resource "google_cloud_scheduler_job" "keep_alive" {
  name             = "api-keep-alive"
  description      = "Wake the API and read from Qdrant weekly, so the free cluster stays active"
  schedule         = var.keep_alive_schedule
  time_zone        = "Asia/Kolkata"
  attempt_deadline = "320s"
  region           = var.region

  http_target {
    http_method = "GET"
    uri         = "${module.api.uri}/readyz"

    oidc_token {
      service_account_email = local.sa.scheduler
      audience              = module.api.uri
    }
  }

  retry_config {
    retry_count = 2
  }
}

resource "google_cloud_scheduler_job" "stop_database" {
  name             = "stop-database"
  description      = "Stop the demo database every night, whatever was left running"
  schedule         = var.sql_stop_schedule
  time_zone        = "Asia/Kolkata"
  attempt_deadline = "60s"
  region           = var.region

  http_target {
    http_method = "PATCH"
    uri         = "https://sqladmin.googleapis.com/v1/projects/${var.project_id}/instances/${google_sql_database_instance.facts.name}"
    body        = base64encode(jsonencode({ settings = { activationPolicy = "NEVER" } }))
    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = local.sa.scheduler
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_project_iam_member" "scheduler_stops_database" {
  project = var.project_id
  role    = "roles/cloudsql.editor"
  member  = "serviceAccount:${local.sa.scheduler}"
}
