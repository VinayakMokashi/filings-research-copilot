# The four Cloud Run services (ADR-0031): a public web UI and MCP server in front of a
# private API, and a private worker that only Pub/Sub may call. Each runs as its own
# account and reads only its own secrets. Images are rolled out by the deploy workflow.

locals {
  vpc = {
    network    = google_compute_network.copilot.id
    subnetwork = google_compute_subnetwork.run.id
  }
  common_env = {
    FRC_ENV        = "prod"
    FRC_LOG_FORMAT = "json"
    HF_HUB_OFFLINE = "1" # every model file is built into the image
  }

  api_secrets = merge(
    {
      GROQ_API_KEY        = "groq-api-key"
      LANGFUSE_PUBLIC_KEY = "langfuse-public-key"
      LANGFUSE_SECRET_KEY = "langfuse-secret-key"
      FRC_QDRANT_URL      = "qdrant-url"
      FRC_QDRANT_API_KEY  = "qdrant-read-api-key"
      FRC_FACTS_URL       = "facts-url"
    },
    var.cerebras_fallback ? { CEREBRAS_API_KEY = "cerebras-api-key" } : {},
  )
  mcp_secrets = {
    FRC_QDRANT_URL     = "qdrant-url"
    FRC_QDRANT_API_KEY = "qdrant-read-api-key"
  }
  worker_secrets = {
    FRC_QDRANT_URL     = "qdrant-url"
    FRC_QDRANT_API_KEY = "qdrant-write-api-key"
    SEC_USER_AGENT     = "sec-user-agent"
  }

  secret_readers = merge(
    { for secret in values(local.api_secrets) : "api/${secret}" => { sa = local.sa.api, secret = secret } },
    { for secret in values(local.mcp_secrets) : "mcp/${secret}" => { sa = local.sa.mcp, secret = secret } },
    { for secret in values(local.worker_secrets) : "worker/${secret}" => { sa = local.sa.worker, secret = secret } },
  )
}

resource "google_secret_manager_secret_iam_member" "readers" {
  for_each = local.secret_readers

  secret_id = each.value.secret
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa}"
}

module "api" {
  source = "../../modules/cloud-run-service"

  name            = "api"
  region          = var.region
  service_account = local.sa.api
  memory          = "2Gi"
  max_instances   = 1 # conversations live in memory (ADR-0031); the load test sizes this
  timeout_seconds = 300
  vpc             = local.vpc
  env = merge(local.common_env, {
    FRC_API_STATE                = "firestore"
    FRC_LLM_DISK_CACHE           = "false"
    FRC_API_TRACE_FILE           = "false"
    GOOGLE_CLOUD_PROJECT         = var.project_id
    LANGFUSE_BASE_URL            = "https://us.cloud.langfuse.com"
    LANGFUSE_TRACING_ENVIRONMENT = "production"
  })
  secret_env = local.api_secrets
  invokers = [
    "serviceAccount:${local.sa.ui}",
    "serviceAccount:${local.sa.mcp}",
    "serviceAccount:${local.sa.scheduler}",
  ]

  depends_on = [google_secret_manager_secret_iam_member.readers]
}

module "ui" {
  source = "../../modules/cloud-run-service"

  name             = "ui"
  region           = var.region
  service_account  = local.sa.ui
  memory           = "512Mi"
  max_instances    = 2
  timeout_seconds  = 3600 # Streamlit's websocket stays open for a visit
  session_affinity = true
  public           = true
  env = {
    FRC_ENV          = "prod"
    FRC_LOG_FORMAT   = "json"
    FRC_API_URL      = "https://${local.host.api}"
    FRC_API_ID_TOKEN = "true"
  }
}

module "mcp" {
  source = "../../modules/cloud-run-service"

  name            = "mcp"
  region          = var.region
  service_account = local.sa.mcp
  memory          = "1Gi"
  max_instances   = 1
  timeout_seconds = 300
  public          = true
  env = merge(local.common_env, {
    FRC_API_URL           = "https://${local.host.api}"
    FRC_API_ID_TOKEN      = "true"
    FRC_MCP_ALLOWED_HOSTS = local.host.mcp
  })
  secret_env = local.mcp_secrets

  depends_on = [google_secret_manager_secret_iam_member.readers]
}

module "worker" {
  source = "../../modules/cloud-run-service"

  name            = "worker"
  region          = var.region
  service_account = local.sa.worker
  memory          = "2Gi"
  max_instances   = 1
  concurrency     = 1 # one filing at a time
  timeout_seconds = 600
  env = merge(local.common_env, {
    FRC_FILINGS_BUCKET = google_storage_bucket.filings.name
  })
  secret_env = local.worker_secrets
  invokers   = ["serviceAccount:${local.sa.pubsub}"]

  depends_on = [google_secret_manager_secret_iam_member.readers]
}

# The API keeps quotas, the answer cache and feedback in Firestore.
resource "google_project_iam_member" "api_uses_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.sa.api}"
}

# The worker keeps each filing it downloads.
resource "google_storage_bucket_iam_member" "worker_writes_filings" {
  bucket = google_storage_bucket.filings.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.sa.worker}"
}
