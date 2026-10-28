# Infrastructure

Every Google Cloud resource of the deployment, in Terraform. The design is in [ADR-0031](../../docs/decisions/0031-google-cloud-topology.md); how to apply it is in the [deploy runbook](../../docs/runbooks/deploy.md).

| Path | What | State prefix |
|---|---|---|
| `bootstrap/` | APIs, the monthly budget, the state and data buckets, the image registry, workload identity federation for GitHub Actions, one service account per service, empty secrets, the billing export's dataset | `bootstrap` |
| `envs/prod/` | The VPC and the demo database's private address, Cloud SQL, Firestore, buckets, Pub/Sub, the four Cloud Run services and who may call them, Cloud Scheduler, alerts and a dashboard | `envs/prod` |
| `modules/cloud-run-service/` | A Cloud Run service that scales to zero; Terraform owns its configuration, the deploy workflow owns its image | |

- **State** lives in the versioned bucket `gs://filings-research-copilot-tfstate`.
- **Checks.** CI checks the formatting and validates every root without its backend.
- **Applies** are run by hand by the project owner, through the project's own gcloud configuration.
- **Secrets.** Terraform creates the secrets empty, and their values never pass through it.
