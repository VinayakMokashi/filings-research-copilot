output "workload_identity_provider" {
  description = "For google-github-actions/auth (repository variable GCP_WIF_PROVIDER)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Repository variable GCP_DEPLOYER_SA."
  value       = google_service_account.deployer.email
}

output "registry" {
  description = "Image registry path (repository variable GCP_REGISTRY)."
  value       = "${google_artifact_registry_repository.images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "data_bucket" {
  description = "Where the API image's data bundle lives (repository variable GCP_DATA_BUCKET)."
  value       = google_storage_bucket.data.name
}

output "runtime_service_accounts" {
  description = "The service accounts the services, the scheduler and Pub/Sub act as."
  value       = { for k, sa in google_service_account.runtime : k => sa.email }
}
