# Create and change the Google Cloud deployment

How the project, its foundations and its services come into being, and how to change them. The design is in [ADR-0031](../decisions/0031-google-cloud-topology.md); the Terraform is in [`infra/terraform/`](../../infra/terraform/README.md).

| | |
|---|---|
| Project | `filings-research-copilot` |
| Region | `asia-south1` (Mumbai) |
| gcloud configuration | `frc`, used by every command below; no other configuration is changed |
| Terraform state | `gs://filings-research-copilot-tfstate` (versioned) |
| Images | `asia-south1-docker.pkg.dev/filings-research-copilot/images/<service>:<commit>` |
| Budget | $15 a month, measured before credits; emails at 50%, 90% and 100% of actual spend and at 100% of forecast |

Everything here is done by the project owner. Terraform authenticates with the owner's gcloud login, so no key file exists.

## 1. The project, and the budget before anything else

Created once, with gcloud, in this order. The budget exists before any resource that can cost money.

```bash
gcloud config configurations create frc --no-activate
export CLOUDSDK_ACTIVE_CONFIG_NAME=frc          # this shell only
gcloud config set account <the owner's account>
gcloud config set project filings-research-copilot

gcloud projects create filings-research-copilot --name="Filings Research Copilot"
gcloud billing projects link filings-research-copilot --billing-account=<BILLING_ACCOUNT_ID>
gcloud services enable billingbudgets.googleapis.com cloudresourcemanager.googleapis.com \
    serviceusage.googleapis.com
gcloud billing budgets create --billing-account=<BILLING_ACCOUNT_ID> \
    --display-name="filings-research-copilot monthly" --budget-amount=15USD \
    --filter-projects=projects/<PROJECT_NUMBER> --calendar-period=month \
    --credit-types-treatment=exclude-all-credits \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0 --threshold-rule=percent=1.0,basis=forecasted-spend
gcloud storage buckets create gs://filings-research-copilot-tfstate --location=ASIA-SOUTH1 \
    --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://filings-research-copilot-tfstate --versioning
```

The budget and the bucket are then adopted by Terraform with `import` blocks in `bootstrap/imports.tf`, written with the budget's ID (`gcloud billing budgets list --billing-account=<BILLING_ACCOUNT_ID>`).

## 2. Apply the bootstrap

```bash
export GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)   # valid for an hour
export TF_VAR_billing_account=<BILLING_ACCOUNT_ID>                    # never committed

terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan
terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan
```

This creates:

- the APIs;
- the image registry and the data bucket;
- workload identity federation for this repository's `main` branch;
- the service accounts and the empty secrets;
- the billing export's dataset.

The outputs give the values for the repository's variables (`GCP_WIF_PROVIDER`, `GCP_DEPLOYER_SA`, `GCP_REGISTRY`, `GCP_DATA_BUCKET`), set with `gh variable set`.

## 3. Add the secrets' values

Terraform creates every secret empty, so no value ever enters its state. A value goes in from a `.env` line without being printed:

```bash
grep '^CLOUD_GROQ_API_KEY=' .env | cut -d= -f2- | tr -d '\r\n' \
  | gcloud secrets versions add groq-api-key --data-file=-
```

| Secret | Read by | Value |
|---|---|---|
| `groq-api-key`, `cerebras-api-key` | `api` | The cloud's own keys; Cerebras only if the fallback is on |
| `langfuse-public-key`, `langfuse-secret-key` | `api` | The cloud's own Langfuse key pair |
| `qdrant-url`, `qdrant-read-api-key` | `api`, `mcp` | The cluster's endpoint and its read-only key |
| `qdrant-write-api-key` | `worker` | The cluster's read-write key |
| `sec-user-agent` | `worker` | The SEC EDGAR contact, sent only to sec.gov |
| `facts-url` | `api` | The `facts_reader` URL on the database's private address (step 4) |
| `sql-admin-password` | the owner | The database's `postgres` password, generated straight into the secret |

Each service may read only its own secrets (`envs/prod/services.tf`). After a rotation, disable the old version: `gcloud secrets versions disable <version> --secret=<name>`.

## 4. Apply the environment

A revision can't start while a secret it reads has no version, and the `facts-url` secret needs the database's private address. So the database goes first:

```bash
export TF_VAR_alert_email=<where alerts go>    # never committed
terraform -chdir=infra/terraform/envs/prod init
terraform -chdir=infra/terraform/envs/prod apply \
    -target=google_sql_database_instance.facts -target=google_sql_database.facts
terraform -chdir=infra/terraform/envs/prod output database_private_address
# add the facts-url secret with that address (step 3), then everything else:
terraform -chdir=infra/terraform/envs/prod plan -out=prod.tfplan
terraform -chdir=infra/terraform/envs/prod apply prod.tfplan
```

The services start on Google's sample image; the first deploy replaces it. A deploy changes only the image, which Terraform ignores, and `demo-up` and `demo-down` change only whether the database runs, which it ignores too. So a plan right after either should say "No changes".

## Costs

- **Idle:** everything scales to zero and the database is stopped, so an idle month should cost about $3 to $4, mostly the database's 10 GB of storage ([ADR-0031](../decisions/0031-google-cloud-topology.md)).
- **If a budget email arrives:** check whether the database was left running (the dashboard's "Demo database up" tile), then Cloud Run's request counts.
