# Ingestion as events (ADR-0031): a request to index a filing is a Pub/Sub message,
# pushed to the worker with a signed token. Deliveries retry with backoff; after five
# attempts a message moves to the dead-letter topic, which an alert watches.

locals {
  pubsub_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic" "ingest" {
  name                       = "ingest"
  message_retention_duration = "604800s"
}

resource "google_pubsub_topic" "ingest_dead_letter" {
  name                       = "ingest-dead-letter"
  message_retention_duration = "604800s"
}

resource "google_pubsub_subscription" "ingest_push" {
  name                 = "ingest-push"
  topic                = google_pubsub_topic.ingest.id
  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${module.worker.uri}/pubsub/ingest"
    oidc_token {
      service_account_email = local.sa.pubsub
      audience              = module.worker.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.ingest_dead_letter.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # never expires
  }
}

# Messages that failed five times wait here to be read and replayed by hand.
resource "google_pubsub_subscription" "ingest_dead_letter" {
  name                       = "ingest-dead-letter"
  topic                      = google_pubsub_topic.ingest_dead_letter.id
  message_retention_duration = "604800s"
  ack_deadline_seconds       = 60

  expiration_policy {
    ttl = ""
  }
}

# Pub/Sub's own agent forwards failed messages and signs the push tokens.
resource "google_pubsub_topic_iam_member" "agent_publishes_dead_letters" {
  topic  = google_pubsub_topic.ingest_dead_letter.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "agent_acks_forwarded" {
  subscription = google_pubsub_subscription.ingest_push.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}

resource "google_service_account_iam_member" "agent_signs_push_tokens" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.sa.pubsub}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.pubsub_agent
}
