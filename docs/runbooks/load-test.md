# Load-test the deployed API

Step 8.7 measures what the deployment takes before it slows, refuses or scales. The model quota is left alone: the test runs on cached answers, so the models are never asked ([`loadtest/locustfile.py`](../../loadtest/locustfile.py)).

## What it does

1. **Warm-up.** It asks six questions once each: the web UI's four examples and two of the SQL set's, all the project's own. Their answers go into the answer cache in Firestore. These are the test's only model calls, about six answers' worth of the day's free quota.
2. **The load.** Simulated visitors, each with its own visitor id, then:
   - ask those questions again (6 parts in 10), which the API serves from the cache, at no quota;
   - read cited pages (3 in 10);
   - check health (1 in 10).

   Each waits 2 to 8 seconds between requests. The measured path is Cloud Run, the API's code and Firestore.

What it doesn't measure is a fresh answer's time. That is set by the models (copilot v2's latency report: 4.0 s at the median, 47 s at the 95th percentile). The API also runs one fresh question at a time per instance (ADR-0020), so fresh answers queue at one instance whatever the load test shows.

## Run it

The API is private, so each request carries an ID token. A project owner's gcloud login mints one that lasts an hour.

```bash
export CLOUDSDK_ACTIVE_CONFIG_NAME=frc
export LOAD_TEST_TOKEN="$(gcloud auth print-identity-token)"
API=https://api-<project number>.asia-south1.run.app

# A gentle start, then the real run
uvx locust -f loadtest/locustfile.py --host "$API" --users 5 --spawn-rate 1 --run-time 2m --headless
uvx locust -f loadtest/locustfile.py --host "$API" --users 30 --spawn-rate 2 --run-time 10m \
    --headless --csv dist/load-test
```

While it runs, watch the dashboard ("Filings Research Copilot" in Cloud Monitoring), which shows:

- requests by response class;
- the 95th percentile of latency;
- instances;
- memory.

## What to record

Record these in the Phase 8 report:

- the requests per second the API served;
- the median and 95th percentile per endpoint (`dist/load-test_stats.csv`);
- the failure rate;
- instance count and peak memory.

Then size the services from them: the API's memory and its maximum instances, and the UI's.

Things to watch:

- **Cold starts.** The first request after an idle spell includes the instance's start; the first minute of the run shows it.
- **One API instance** (`max_instances = 1`) serves every cached answer. If its latency climbs with the users, the CPU, not the models, is the limit.
- **429s** mean a quota stopped a request. Cached answers take no quota, so a 429 is a bug.

The test checked itself against a local stand-in of these endpoints: the warm-up and every request type, with no failures.
