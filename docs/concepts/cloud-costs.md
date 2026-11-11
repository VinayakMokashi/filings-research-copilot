# Cloud costs: reading what a deployment bills

> Read the bill line by line, from Google's billing export, to learn what an idle deployment, a demo and a visitor each cost, and which settings decide it.

**Lands in:** Phase 8 · **Code:** `infra/terraform/bootstrap/main.tf`, `infra/terraform/envs/prod/`, `infra/terraform/modules/cloud-run-service/`, `.github/workflows/deploy.yml`

## What it is

A cloud bill is a list of SKUs: priced units such as a second of CPU, a byte-second of storage, a byte sent to the internet, or a request.

- **Usage times price is the gross cost.**
- **Credits** are negative amounts set against it. Two kinds show up here:
  - a trial's promotional credit, which pays almost everything until it runs out;
  - free tiers, which pay the first part of each month's use and never end.
- **The net** is what the card pays.
- **The billing export** copies every line into BigQuery: one row per project, SKU and hour of use, with the usage, its unit, the gross cost and a list of credits (type, name, amount). The bill can then be queried like any table.

## Why we need it here

[ADR-0016](../decisions/0016-deploy-on-google-cloud.md) chose Google Cloud on a promise: services that scale to zero cost almost nothing while idle, and the database runs only for demos. Phase 8 is done when an idle month costs close to nothing.

Only the bill can confirm that, and the trial makes the bill's own total useless: the net stays $0.00 whatever runs. So step 8.9 reads the gross cost, SKU by SKU.

## How it works

**Turning the export on** is a console step: Billing, then Billing export, then BigQuery export, then Standard usage cost, choosing a dataset.

- A dataset in the US multi-region also receives the previous month's data, backfilled over up to five days.
- The table's name contains the billing account's id, so queries name it with a wildcard: `` `<project>.billing_export.gcp_billing_export_v1_*` ``.

**What each kind of resource bills for:**

| Kind | Bills | Here |
|---|---|---|
| Stored | All the time | The stopped database's 10 GB SSD ($2.07 a month); images in the registry; files in a bucket; secret versions |
| Running | While it runs | A Cloud SQL instance, from its start request to its stop request; a Cloud Run instance while any request is in flight |
| Moving | Per byte | Egress to the internet, including to a CI runner |
| Counted | Per request or per job | Uptime checks, scheduler jobs, secret reads: all inside free tiers here |

**Free tiers are monthly and per billing account.** Every project on the account draws on them.

- So the same SKU can be free one day and charged the next.
- The registry's storage started costing on 9 November, when the month's free 0.5 GB had been used across the account.

**Reading an event.** Hourly rows show *when* something cost more than a quiet hour does. The logs then say *what* it was: a visitor's websocket, the weekly keep-alive, a check run from the laptop.

```sql
SELECT DATE(usage_start_time) AS day, service.description AS service, sku.description AS sku,
       SUM(cost) AS gross,
       SUM((SELECT IFNULL(SUM(c.amount), 0) FROM UNNEST(credits) c)) AS credits
FROM `filings-research-copilot.billing_export.gcp_billing_export_v1_*`
WHERE project.id = 'filings-research-copilot'
GROUP BY day, service, sku
ORDER BY day, gross DESC
```

## Where it lives in the code

| File | What it decides |
|---|---|
| `infra/terraform/bootstrap/main.tf` | The $15 monthly budget, before credits; the export's dataset; the registry's cleanup policy (three newest versions kept, the rest deleted after a week) |
| `infra/terraform/modules/cloud-run-service/main.tf` | Request-based billing (`cpu_idle = true`) and scaling to zero |
| `infra/terraform/envs/prod/services.tf` | Each service's CPU, memory and request timeout. The UI's 3,600 s bounds one websocket |
| `src/copilot/ui/app.py`, `src/copilot/ui/static/paused.html` | The UI's idle limit: a page without input for 15 minutes (`FRC_UI_IDLE_MINUTES`) leaves for a static page, which closes its websocket |
| `infra/terraform/envs/prod/scheduler.tf` | The nightly database stop and the weekly keep-alive |
| `.github/workflows/deploy.yml` | The start check, which runs the image the build loaded instead of downloading it |

## How we measured it

The [deployment report](../eval/deployment.md#costs) has the full tables:

- **An idle week,** 3 to 9 November: $0.56 gross. Without one visit, the demo hour's spill-over and one check, it was $0.49, which is $2.15 a month. 96% of that is the stopped database's storage.
- **A demo hour** on 10 November: $0.0138. Of that, $0.0126 is instance time: 3,607 s, matching the start-to-stop requests to the second.
- **One visit** on 4 November: one tab open for 33 minutes, $0.052. An open page costs $0.09 an hour.
- **The idle limit** on 11 November: a page left without input held its websocket for 900.7 s, then went to the paused page and opened no other. A forgotten tab now costs about $0.023 once.
- **A deploy** paid $0.042 of registry egress until the start check stopped downloading the image.

## Pitfalls we hit

- **The trial hides everything.** The net was $0.00 every day; only the gross and the credits' types say what comes after the trial.
- **The export spreads instance time over four-hour blocks.** Three quarters of the demo hour of 10 November (00:00 to 01:01 UTC) is booked on 9 November.
- **A websocket is a request.** With request-based billing, an open Streamlit page keeps the UI's CPU billed. A tab left open for a day would have cost about 30 times what the rest of the idle deployment does. Streamlit has no idle timeout of its own, so the page now leaves for a static page after 15 minutes without input; leaving a page is what closes its websocket.
- **A browser may decide first.** Measuring the idle limit in an ordinary Chrome tab failed once: Chrome discarded the background tab after about 11 minutes to save memory, which closed the websocket too. A headless browser, which discards nothing, measured the limit itself.
- **A check downloaded what it had just built.** The deploy's start check ran the API image from the registry, because the build pushed without loading it: 0.376 GB of egress a deploy.
- **Free tiers are shared.** The registry's storage started costing on 9 November, before this project alone had used the free 0.5 GB: the account's other projects draw on it too.

## Review questions

1. A stopped Cloud SQL instance still costs about $2 a month here. What does it pay for, and what would a public IPv4 address add?
2. During the trial the net bill is $0.00. Which numbers tell you what the deployment will cost after it, and which credits stay?
3. One 33-minute visit cost as much as about 30 quiet days of Cloud Run. Why, and what bounds it?
4. A demo window ran from 00:00 to 01:01 UTC, yet most of its instance time is booked the day before. Why, and how should such a window be read?
5. Why did each deploy pay for egress from the registry, when Cloud Run pulling the same image costs nothing?

## References

- Google Cloud: [exporting billing data to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery), [the standard usage cost table](https://cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Cloud SQL pricing](https://cloud.google.com/sql/pricing), [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing), [the free tier](https://cloud.google.com/free/docs/free-cloud-features).
- [ADR-0031](../decisions/0031-google-cloud-topology.md); [Cloud Run](cloud-run.md).
