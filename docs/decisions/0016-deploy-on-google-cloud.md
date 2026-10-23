# ADR-0016: Deploy on Google Cloud, with services that scale to zero

- **Status:** Accepted
- **Date:** 2026-10-23
- **Phase:** 8 (decided at the close of Phase 4)
- **Supersedes:** [ADR-0003](0003-aws-demo-windows.md)

## Context

[ADR-0003](0003-aws-demo-windows.md) planned a production-shaped AWS stack that would come up only for demos, because ECS services, a load balancer and RDS cost $80 to $100 a month left running. Nothing cloud-specific has been built since: the project runs locally with Docker Compose, and Phase 8 is four phases away, so the choice of cloud can change at no cost now.

Two things favour Google Cloud:

- **Credit and familiarity.** The builder already uses Google Cloud and has its free-trial credit of $300, valid for 90 days from activation.
- **Scaling to zero.** Cloud Run runs containers that scale to zero when no requests arrive and serves each one over HTTPS. On AWS, costing nothing while idle meant tearing the stack down; on Cloud Run the services can stay deployed.

## Options considered

| Option | While idle | Pros | Cons |
|---|---|---|---|
| AWS in demo windows ([ADR-0003](0003-aws-demo-windows.md)) | Nothing, once torn down | Production shape; the most widely used cloud | Bring-up takes minutes; HTTPS needed a domain or CloudFront; no credit to draw on |
| Google Cloud with everything always on | A database running around the clock | Always reachable | Pays for an idle database |
| **Google Cloud: services that scale to zero, the database only for demos** | Storage, and little else | Services stay deployed, reachable, and serve HTTPS themselves; the trial credit; a cloud the builder already uses | The credit expires after 90 days; Cloud SQL has no free tier |

## Decision

Deploy Phase 8 on Google Cloud in `asia-south1` (Mumbai), the region closest to the builder, as it was on AWS:

| Need | Service |
|---|---|
| API, web UI and MCP server | Cloud Run services, scaling to zero |
| Ingestion | A Cloud Run worker fed by Pub/Sub, with a dead-letter topic |
| App state, and the facts tables in production | Cloud SQL for PostgreSQL, started only for demos |
| Raw filings and backups | Cloud Storage |
| Per-visitor quotas | Firestore |
| Container images | Artifact Registry, with vulnerability scanning |
| Secrets | Secret Manager |
| Logs, metrics and alerts | Cloud Logging and Cloud Monitoring, and a Cloud Billing budget alert |
| Deploys | GitHub Actions through Workload Identity Federation, with no service-account keys |
| Infrastructure as code | Terraform with the Google provider |

Qdrant Cloud, Groq and Langfuse stay external services, as before.

## Consequences

- **Demo windows shrink to the database.** The Cloud Run services stay deployed and cost nothing between visits. `demo-up` and `demo-down` start and stop the Cloud SQL instance, whose storage stays, and a scheduled job stops it if it is left running past a time limit.
- **HTTPS comes with Cloud Run.** Every service has an HTTPS address, and a custom domain becomes optional, so ADR-0003's choice between a domain and CloudFront falls away.
- **The credit is time-limited.** It lasts 90 days from activation, so Phase 8's measurements (the cost of an idle month and of a demo, the load test) should run inside that window. After it, the budget alert and the always-free tier apply.
- **No long-lived cloud credentials.** Each service runs as its own least-privilege service account, and GitHub deploys through Workload Identity Federation.
- ADR-0010's planned SQS-driven worker becomes the Pub/Sub-fed Cloud Run worker.
- The plan's Phase 8 steps, its prerequisites, technical choices and risks, the README, the glossary and the project page now describe Google Cloud. The planned guides become `cloud-run.md`, `terraform-basics.md` and `workload-identity-federation.md`.
- Costs are measured in Phase 8 and recorded in its evaluation report.

## References

- Cloud Run pricing: https://cloud.google.com/run/pricing
- Google Cloud free trial and free tier: https://cloud.google.com/free/docs/free-cloud-features
- Starting and stopping Cloud SQL instances: https://cloud.google.com/sql/docs/postgres/start-stop-restart-instance
- Workload Identity Federation with deployment pipelines: https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
- The `google-github-actions/auth` action: https://github.com/google-github-actions/auth
