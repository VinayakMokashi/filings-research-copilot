# State that outlives instances (ADR-0031): Firestore for the quotas, the answer cache
# and feedback; Cloud Storage for downloaded filings and for backups.

resource "google_firestore_database" "default" {
  name                    = "(default)"
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_ENABLED"
  deletion_policy         = "ABANDON"
}

# Cached answers expire on their own: Firestore deletes a document once its
# expires_at has passed (within about a day).
resource "google_firestore_field" "answers_expire" {
  database   = google_firestore_database.default.name
  collection = "answers"
  field      = "expires_at"

  ttl_config {}

  # A TTL field needs no single-field index.
  index_config {}
}

# Quota counters expire two days after their day (copilot.api.firestore).
resource "google_firestore_field" "quota_days_expire" {
  database   = google_firestore_database.default.name
  collection = "quotas"
  field      = "expires_at"

  ttl_config {}
  index_config {}
}

resource "google_firestore_field" "quota_visitors_expire" {
  database   = google_firestore_database.default.name
  collection = "visitors"
  field      = "expires_at"

  ttl_config {}
  index_config {}
}

resource "google_storage_bucket" "filings" {
  name                        = "${var.project_id}-filings"
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# Qdrant collection snapshots and database dumps; old copies go after six months.
resource "google_storage_bucket" "backups" {
  name                        = "${var.project_id}-backups"
  location                    = upper(var.region)
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type = "Delete"
    }
  }
}
