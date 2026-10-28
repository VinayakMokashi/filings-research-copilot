# The facts tables for demo windows (ADR-0031): Cloud SQL for PostgreSQL, stopped
# outside them. `demo-up` and `demo-down` start and stop the instance, so Terraform
# ignores whether it is running; a Cloud Scheduler job stops it every night.

resource "google_sql_database_instance" "facts" {
  name                = "facts"
  database_version    = "POSTGRES_18"
  region              = var.region
  deletion_protection = true

  settings {
    edition           = "ENTERPRISE"
    tier              = var.sql_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 10
    disk_autoresize   = false
    activation_policy = "NEVER"

    deletion_protection_enabled = true

    ip_configuration {
      ipv4_enabled    = false # a private address only
      private_network = google_compute_network.copilot.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "21:00" # UTC, 02:30 in India; runs only while the instance is up
      point_in_time_recovery_enabled = false
      backup_retention_settings {
        retained_backups = 7
      }
    }

    maintenance_window {
      day  = 7 # Sunday
      hour = 21
    }

    insights_config {
      query_insights_enabled = false
    }
  }

  lifecycle {
    ignore_changes = [settings[0].activation_policy]
  }

  depends_on = [google_service_networking_connection.services]
}

# The C collation is set on each text column by the loader's schema, so text sorts in
# SQLite's byte order whatever the database's default (copilot.facts.postgres).
resource "google_sql_database" "facts" {
  name     = "facts"
  instance = google_sql_database_instance.facts.name
}
