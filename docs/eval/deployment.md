# The deployment on Google Cloud: releases, a demo window, load, and security

Phase 8, steps 8.5 to 8.8, measured on the live services on 2 November 2026. The costs (step 8.9) follow once the billing export has an idle week to read.

## Question

Does the deployment of [ADR-0031](../decisions/0031-google-cloud-topology.md) work as designed?

- Releases go out by themselves and roll back when they fail ([ADR-0032](../decisions/0032-continuous-deployment.md)).
- The demo database starts and stops on demand and every night.
- One API instance serves the public demo under load.
- Every account holds only what it uses.

## Setup

- **Region:** `asia-south1`. The services, the database, the buckets and Firestore are all there.
- **Services:** four on Cloud Run, all scaling to zero.
  - The UI and the MCP server are public.
  - The API is private. Only the UI's, the MCP server's, the scheduler's and the deployer's accounts may call it.
  - The worker is private. Only Pub/Sub's push account and the deployer may call it.
- **Data:**
  - Qdrant Cloud's free cluster holds the doc agent's 23,585 chunks.
  - Cloud SQL holds the facts tables for demo windows.
  - Firestore holds the quotas, the answer cache and feedback.
- **Models:** Groq's free tier, with Cerebras as a fallback capped at $0.50 a day ([ADR-0033](../decisions/0033-capped-paid-fallback.md)).
- **Checks** were run from a laptop in India: the deploy's own smoke tests, calls with the owner's identity, a demo window, the scheduler's jobs run by hand, a rollback by hand, and two load tests with Locust.

## Results

### Releases

Five deploys ran on 2 November. Two failed, and both failures changed the pipeline.

| Deploy | Outcome | What it showed |
|---|---|---|
| 1 | The API's new revision never started | The image lacked two committed reference files. Cloud Run kept the traffic on the previous revision. |
| 2 | Rolled out, then rolled back | The smoke test's `/healthz` got the front end's 404 (below). The rollback returned every service to its previous revision. |
| 3 to 5 | Every smoke test passed | The API reports its commit and passes readiness; the worker, the MCP server and the UI answer. |

- **The start check.** Deploy 1 led to one: the new API image must start on the runner, with its state in memory, before anything rolls out. It passed in deploys 2 to 5.
- **A rollback by hand** moved the UI's traffic to an earlier revision in 10 s, and back to the latest in 10 s.
- **After a deploy,** both Terraform roots plan "No changes": a deploy changes only images, which Terraform ignores.

### Live checks

| Check | Result |
|---|---|
| UI health | `ok` in 1.4 s |
| MCP server | `initialize` in 0.2 s; three tools listed; `search_filings` returned three passages from Qdrant Cloud in 15.1 s, a cold start included |
| API readiness | all six checks pass: the facts database, the pages, the Groq key, the Cerebras key, Qdrant Cloud and Firestore |
| A fresh question (one of the UI's examples) | answered on the data route in 6.6 s |
| The same question again | served from the answer cache in Firestore in 0.7 s, with no model call |
| The API without a token | 403 |

### A demo window

| Step | Time |
|---|---|
| `demo-up`: start the instance | 10 min 27 s |
| `demo-down`: stop it | 42 s |
| The nightly job, run by hand: stop it | within a minute; the job answered 200 |

- **The data agent on PostgreSQL.** During the window, a fresh data question was answered in 5.4 s:
  - the API logged no fallback to the file;
  - Cloud SQL counted transactions on the `facts` database in the minutes of the question (9, then 22), after 0 the minute before.
- **Outside the window,** the API logged its fallback to the file, and answered from it.
- **The weekly keep-alive job,** run by hand, read the API's `/ready` and answered 200.

### Load

**Setup.** Locust ran 30 simulated visitors for 10 minutes, each waiting 2 to 8 s between requests. Each visitor:

- repeated questions the warm-up had answered, served from the answer cache (6 in 10 requests);
- read cited pages (3 in 10);
- checked health (1 in 10).

Locust times a streamed reply to its first byte, which for a cached answer is the whole reply. Cloud Run's request latencies cover the whole stream.

**The final run** had 3,540 requests, 5.9 a second, with no failure. Locust's times, in milliseconds:

| Endpoint | Requests | Median | 95th | 99th | Max |
|---|---|---|---|---|---|
| `/v1/ask`, from the cache | 2,142 | 49 | 65 | 130 | 876 |
| `/v1/sources/{doc}/{page}` | 1,034 | 43 | 62 | 120 | 838 |
| `/health` | 358 | 40 | 59 | 100 | 165 |
| All | 3,540 | 46 | 65 | 130 | 876 |

**Cloud Run's metrics** for the same window, per minute:

- all 3,540 requests answered 2xx;
- the API's own latency at most 14 ms at the median, 28 ms at the 95th percentile and 49 ms at the 99th;
- one instance throughout;
- memory at most 49% of 2 GiB, and CPU at most 6%, both at the 99th percentile.

**The first 30-visitor run** found a flaw in the test, and one in the UI.

- **The test's assumption.** One of the UI's examples asked about Netflix's 2022 10-K. The corpus holds the 2015 and 2017 ones, so the copilot correctly declined. A declined answer is never cached, so each simulated visitor who drew that question started a fresh run.
- **What those runs did:**
  - they queued behind the API's one-run-at-a-time lock. 45 of 682 asks got an error event, and the API logged no failure in that window, so these were its "busy" reply to a question that waits more than two minutes for its turn;
  - Groq refused 224 model calls during that run, and every one went to Cerebras: $0.1637, at most $0.0027 a call. With the warm-ups before it, the paid calls came to $0.1996, within the day's $0.50 cap.
- **Fixes:**
  - the example now asks about the 2017 10-K, and was answered in 11.3 s with a citation;
  - the warm-up now reads the copilot's own `answered` flag, and the load counts a cache miss as a failure.

**Sizing.** No change.

- One API instance carried six requests a second of cached traffic at 6% CPU, so what limits fresh answers is the model quota, not the instance.
- One instance is also what keeps conversations in memory (ADR-0031).
- Memory stays at 2 GiB: the cached load used half of it, and a fresh run loads the models on top.

### Visitors behind Google's front end

The UI counts a visitor's quota by the last address in `X-Forwarded-For` ([ADR-0031](../decisions/0031-google-cloud-topology.md)). A throwaway echo service on Cloud Run, since deleted, showed what the container receives. With a forged entry sent, the container saw the forged entry first and the caller's address last. A visitor can't escape the quota by sending the header.

### Security pass

| Check | Result |
|---|---|
| Accounts and roles | One account per service, each reading only its own secrets. The deployer may roll out the four services only (Cloud Run Developer on each). The scheduler holds a two-permission custom role: read and update Cloud SQL instances. Google's default Compute account no longer holds Editor. |
| Keys | None exists. GitHub Actions reaches Google Cloud through workload identity federation, limited to this repository's `main`. |
| The database | Private address only, TLS required. The `facts_reader` user, checked on the instance: SELECT on all 7 tables, write on none, no membership in `cloudsqlsuperuser`, and no right to create roles, databases or tables. `postgres` has no password, and the unused admin secret is gone. |
| The network | The `default` VPC, whose firewall let SSH and RDP in from anywhere, is deleted. The copilot's own VPC has no firewall rule open to the internet. |
| Secrets | Nine secrets, created empty by Terraform, so no value ever enters its state. Values were added from the laptop without being printed. A failed `gcloud` command now hides a password from its error. |
| Images | Trivy on the final commit's API and UI images (the MCP server and the worker are built from the API's): no fixable HIGH or CRITICAL vulnerability, across the Debian 13.7 base and every Python package. |
| The repository | Secret scanning's push protection is on. gitleaks runs in CI. |
| Dependencies | One open Dependabot alert: `diskcache` (CVE-2025-69872, medium), with no patched release. It comes in through DSPy, in the `dev` group only, which no image installs. |

**Registry scan: skipped.** The planned one-off scan with Artifact Registry's own scanner didn't run. gcloud's on-demand scan doesn't support Windows, the machine all of this ran from. The registry's automatic scanning would also have rescanned every image pushed that day, about 20, at $0.26 each, and every later push. Trivy's results above cover the same packages.

## Problems found and fixed

| Problem | Fix |
|---|---|
| Cloud SQL can't create a stopped instance (`400 invalidOperation`) | Created running; `demo-down` stops it once the facts are loaded |
| `facts_reader`, created through Cloud SQL's API, could create roles, databases and tables | The loader revokes the membership and both attributes on every load |
| The API image lacked two reference files | Copied into the image, with a test and a start check |
| Cloud Run's front end answers `/healthz` itself | The endpoints are `/health` and `/ready`, and a test keeps route names off a final "z" |
| `demo-up` gave up while the start went on (gcloud stops waiting at about ten minutes) | The command returns at once, and the script waits up to 25 minutes |
| An apply lost its token midway (gcloud's cached token had minutes left) | The kept state was pushed after a `force-unlock`; the runbook says how to check a token's life |
| Every plan wanted to update the dashboard | The dashboard is written the way Cloud Monitoring stores it |
| A UI example asked about a filing the corpus lacks | An example the copilot answers |

## Costs

Pending: step 8.9 reads them from the billing export, once it has an idle week, and adds them here. Measured so far:

- **Cerebras:** $0.1996, the paid fallback during the load tests and their warm-ups.
- **Google Cloud:** from the billing export, pending.

## Limits

- **One laptop, one day.** The load came from one machine in India. The latencies are what one visitor nearby sees, not a global measure.
- **Cached answers only.** The load test measures Cloud Run, Firestore and the API's code. A fresh answer's time is set by the models: [copilot v2's latency](copilot-v2.md) is 4.0 s at the median and 47 s at the 95th percentile.
- **Two smoke-tested paths aren't in the load:** the MCP server and the worker. Each was checked once.
