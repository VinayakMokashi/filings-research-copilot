# A Cloud Run service that scales to zero. Terraform owns its configuration; the deploy
# workflow owns the image, so a deploy never shows up as drift here (ADR-0031).

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }
}

resource "google_cloud_run_v2_service" "this" {
  name                = var.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection
  # ID tokens for these audiences are accepted too: the deterministic address, which
  # callers know before the service exists.
  custom_audiences = var.audiences

  template {
    service_account                  = var.service_account
    max_instance_request_concurrency = var.concurrency
    timeout                          = "${var.timeout_seconds}s"
    session_affinity                 = var.session_affinity

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    # Direct VPC egress, for private addresses only (the database); everything else
    # leaves Cloud Run directly.
    dynamic "vpc_access" {
      for_each = var.vpc == null ? [] : [var.vpc]
      content {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = vpc_access.value.network
          subnetwork = vpc_access.value.subnetwork
        }
      }
    }

    containers {
      # The first image is Google's sample; every deploy replaces it.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true # CPU is billed only while a request is in flight
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secrets come from Secret Manager at instance start, never from Terraform's state.
      dynamic "env" {
        for_each = var.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.public ? 1 : 0

  name     = google_cloud_run_v2_service.this.name
  location = google_cloud_run_v2_service.this.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(var.invokers)

  name     = google_cloud_run_v2_service.this.name
  location = google_cloud_run_v2_service.this.location
  role     = "roles/run.invoker"
  member   = each.value
}
