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

## The data bundle

The API image carries its data (ADR-0031), from a bundle in the data bucket. It holds:

- facts.db;
- the 84 corpus filings' pages;
- the index card and the corpus's metadata;
- FastEmbed's two model folders.

Build it again whenever any of these changes:

```bash
uv run poe bundle-data                                   # dist/api-data.tar.gz, about 100 MB
uv run poe bundle-data --upload filings-research-copilot-data   # once the bucket exists
```

The archive is deterministic: the same data gives the same SHA-256, and so the same object name (`api-data-<hash>.tar.gz`). `infra/data-bundle.json` records the bundle the images are built from; commit it with the change that needs it. The deploy workflow downloads that object and checks its hash. It then builds the `api` and `mcp` images with `--build-context data=<the extracted bundle>`. Without that context, as in CI's checks and Docker Compose, the images hold no data.

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

## Connect GitHub

After the bootstrap, set the repository's variables from its outputs. None of them is secret: the deploy reaches Google Cloud through workload identity federation.

```bash
for name in workload_identity_provider deployer_service_account registry data_bucket project_number; do
  terraform -chdir=infra/terraform/bootstrap output -raw "$name"; echo
done
gh variable set GCP_PROJECT_ID --body filings-research-copilot
gh variable set GCP_REGION --body asia-south1
gh variable set GCP_PROJECT_NUMBER --body <project_number>
gh variable set GCP_WIF_PROVIDER --body <workload_identity_provider>
gh variable set GCP_DEPLOYER_SA --body <deployer_service_account>
gh variable set GCP_REGISTRY --body <registry>
gh variable set GCP_DATA_BUCKET --body <data_bucket>
```

Setting `GCP_PROJECT_ID` switches deploys on. Until then CI skips them.

## How a release happens

[ADR-0032](../decisions/0032-continuous-deployment.md) sets out the design. On a push to `main` that changes what the images hold, CI's deploy job waits for every check, then runs the [Deploy workflow](../../.github/workflows/deploy.yml). "What the images hold" means `src/`, the Dockerfile, the lock, the router's examples, the results the UI shows, or `infra/data-bundle.json`.

1. **Access.** GitHub's OIDC token becomes an hour of `github-deployer`'s access. No key exists anywhere.
2. **Data.** The data bundle named in `infra/data-bundle.json` is fetched, and its SHA-256 is checked.
3. **Images.** `api` and `mcp` are built with the bundle, `ui` without it. Each is tagged with the commit and pushed.
4. **Rollout.** `api`, then `mcp`, then `ui` get a new revision, which takes all their traffic. Each service's previous revision is noted first.
5. **Smoke tests:**
   - the private API reports this commit at `/healthz` and passes `/readyz`;
   - the MCP server answers an MCP `initialize`;
   - the UI's health endpoint answers.
6. **Rollback.** If anything fails after the rollout, every service's traffic goes back to the revision it replaced.

To deploy without such a change, run it by hand: Actions → Deploy → Run workflow, on `main`.

## Roll back by hand

A rollback moves traffic to an earlier revision; nothing is rebuilt.

```bash
gcloud run revisions list --service=api --region=asia-south1
gcloud run services update-traffic api --to-revisions=<revision>=100 --region=asia-south1
```

The next deploy sends the traffic to the newest revision again. To do that by hand, run `gcloud run services update-traffic api --to-latest --region=asia-south1`.

## Qdrant Cloud

The doc agent's collection is copied from the local Qdrant to the free cluster. The cluster's address and its read-write key come from `.env`'s `CLOUD_QDRANT_URL` and `CLOUD_QDRANT_API_KEY`; the services get their keys from Secret Manager.

```bash
uv run poe copy-collection --snapshot-to filings-research-copilot-backups
```

The copy recreates the collection with the local one's vector settings and payload indexes, then upserts every point in batches. A copy that already holds every point is left alone; an interrupted one finishes on the next run. With `--snapshot-to`, it then takes a snapshot of the copy on the cluster, keeps it in the backups bucket under `qdrant/`, and deletes it from the cluster's small disk.

The free cluster is suspended after a week without use and deleted after four. The scheduler's weekly call to the API's readiness check reads the collection, which keeps the cluster in use. **If the cluster was suspended,** resume it in Qdrant Cloud's console. **If it was deleted:**

1. Create a new free cluster and its two keys (read-only and read-write).
2. Update `CLOUD_QDRANT_URL` and both keys in `.env`.
3. Run `copy-collection` again, from the local Qdrant, or upload the latest snapshot from the backups bucket through the cluster's `POST /collections/fb_page_bge-small/snapshots/upload`.
4. Load the secrets again (step 3).

## Costs

- **Idle:** everything scales to zero and the database is stopped, so an idle month should cost about $3 to $4, mostly the database's 10 GB of storage ([ADR-0031](../decisions/0031-google-cloud-topology.md)).
- **If a budget email arrives:** check whether the database was left running (the dashboard's "Demo database up" tile), then Cloud Run's request counts.
