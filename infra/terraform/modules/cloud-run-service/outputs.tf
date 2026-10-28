output "name" {
  description = "Service name."
  value       = google_cloud_run_v2_service.this.name
}

output "uri" {
  description = "HTTPS address of the service."
  value       = google_cloud_run_v2_service.this.uri
}
