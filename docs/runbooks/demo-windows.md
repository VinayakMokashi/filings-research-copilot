# Demo windows: start and stop the demo database

The deployment's Cloud SQL instance holds the facts tables for the data agent and runs only during demos ([ADR-0031](../decisions/0031-google-cloud-topology.md)). Outside a window, the data agent answers from the facts file the API image carries, with the same answers ([report](../eval/facts-postgres.md)). Each command uses the project's own gcloud configuration (`frc`).

| | |
|---|---|
| Instance | `facts`: PostgreSQL 18, db-f1-micro, 10 GB SSD, private address only |
| Running | about $0.01 an hour |
| Stopped | about $2 a month for its storage; no IP charge, since it has no public address |
| Nightly stop | Cloud Scheduler, 23:30 IST, whatever was left running |
| Alert | an email after four hours up |

## Start a window

```bash
uv run poe demo-up
```

It asks Cloud SQL to start the instance and waits until it runs, usually a minute or two. The API's data agent turns to it with its next question within a minute: a failed connection makes it try the server again only after a minute. Each answer's SQL details then show the query PostgreSQL ran.

## End a window

```bash
uv run poe demo-down
```

The instance stops and its storage stays. Within a minute the data agent is back on the facts file. If you forget, the nightly job stops it at 23:30 IST, and the four-hour alert reminds you before that.

## Load or reload the facts

Do this once, after the first `demo-up`, and again after every rebuild of facts.db:

```bash
uv run poe load-facts-postgres     # the local copy (Compose Postgres), as the facts runbook says
uv run poe demo-up
uv run poe load-facts-cloudsql     # --rotate gives the reader a new password
```

`load-facts-cloudsql` runs four steps:

1. It dumps the local `facts` database to `dist/facts.sql.gz`, with DROP statements, so a reload replaces the tables.
2. It copies the dump to the backups bucket and imports it with `gcloud sql import`, read by the instance's own service account. Nothing connects to the private address from outside Google's network.
3. It gives the `facts_reader` user SELECT on the facts tables, read-only transactions and a 15-second statement timeout. The first run creates the user with a generated password.
4. It puts the reader's URL into the `facts-url` secret, which the API reads at start.

No password is printed. The script passes the reader's password to gcloud as an argument, which is the only way gcloud takes it, but only in a process on your machine.

**After a reload,** the API's running instance keeps the URL it read at start. A new instance reads the new secret version, so after `--rotate`, redeploy the API or wait until it has scaled to zero.

## When something goes wrong

| Symptom | Cause and fix |
|---|---|
| `demo-up` times out | Look at the instance in the console (SQL > facts > Operations). A failed start is retried by running `demo-up` again. |
| Answers' SQL details never show PostgreSQL during a window | The API couldn't connect. Check its logs for `facts_server_unavailable`, then check that the `facts-url` secret has a version and that the API has Direct VPC egress (`envs/prod/services.tf`). |
| The four-hour alert arrives during a long demo | Nothing is wrong; run `demo-down` when the demo ends. |
