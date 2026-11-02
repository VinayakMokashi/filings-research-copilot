# Keyless deploys: GitHub Actions exchanges its OIDC token for a short-lived token of
# the deployer service account. Only this repository's main branch is accepted, and no
# service-account key exists anywhere (ADR-0016, ADR-0031).

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "Deploys from the filings-research-copilot repository"

  depends_on = [google_project_service.this]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "filings-research-copilot"
  display_name                       = "filings-research-copilot"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository"    = "assertion.repository"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.ref"           = "assertion.ref"
  }
  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
    "assertion.ref == 'refs/heads/main'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# One identity per service (ADR-0031). envs/prod grants each one what it needs: the
# secrets it reads, Firestore, the invoker roles between services.
resource "google_service_account" "runtime" {
  for_each = {
    api       = "The copilot's API at runtime"
    ui        = "The web UI at runtime"
    mcp       = "The MCP server at runtime"
    worker    = "The ingestion worker at runtime"
    scheduler = "Cloud Scheduler: the weekly keep-alive and the nightly database stop"
    pubsub    = "Pub/Sub push deliveries to the worker"
  }

  account_id   = "${each.key}-runtime"
  display_name = each.value

  depends_on = [google_project_service.this]
}

resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions deployer"
  description  = "Builds and pushes images and rolls out Cloud Run revisions from main"

  depends_on = [google_project_service.this]
}

resource "google_service_account_iam_member" "deployer_from_github" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_pushes_images" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deployer.member
}

# The image build reads the data bundle.
resource "google_storage_bucket_iam_member" "deployer_reads_data" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.deployer.member
}

# The deployer may roll out revisions of the four services only: envs/prod grants Cloud
# Run Developer on each service (the module's `deployers`), not on the project.

# A new revision runs as its runtime account, so the deployer must be allowed to act as
# the services' accounts (not the scheduler's or Pub/Sub's).
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  for_each = toset(["api", "ui", "mcp", "worker"])

  service_account_id = google_service_account.runtime[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deployer.member
}

# Enabling Compute gives its default service account Editor on the project. Nothing here
# runs as it (each service, the scheduler and Pub/Sub have their own accounts), so it
# keeps no role on the project.
resource "google_project_iam_member_remove" "default_compute_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.this]
}
