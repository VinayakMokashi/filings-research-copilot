output "ui_url" {
  description = "The web UI, public."
  value       = module.ui.uri
}

output "mcp_url" {
  description = "The MCP server's streamable HTTP endpoint, public."
  value       = "https://${local.host.mcp}/mcp"
}

output "api_url" {
  description = "The API, callable only by the UI, the MCP server and the scheduler."
  value       = module.api.uri
}

output "worker_url" {
  description = "The ingestion worker, callable only by Pub/Sub."
  value       = module.worker.uri
}

output "database_private_address" {
  description = "The demo database's private address, for the facts URL secret."
  value       = google_sql_database_instance.facts.private_ip_address
}

output "ingest_topic" {
  description = "Publish a filing to index here."
  value       = google_pubsub_topic.ingest.id
}
