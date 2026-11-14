# The search page's interleaving

How the web UI's Search page compares two rankings, and how to count it ([ADR-0038](../decisions/0038-interleaved-search.md), [guide](../concepts/online-evaluation.md#interleaving)).

## What runs

- **The page:** the UI's Search tab. A reader's words go to `POST /v1/search`, which searches the filings the words name with two rankings, dense (`a`) and hybrid (`b`), interleaves their top results by team draft, and returns 8 passages. No model is called, and no quota is counted.
- **A click:** opening a passage's page (`POST /v1/search/click`) credits the ranking that placed it, once a result.
- **What is kept:** Firestore `interleaving/<search id>`: the teams in list order, how many filings were searched, the two rankings' overlap, and `click_<position>` for each result opened. Never the query.

## Count it

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=frc uv run poe interleaving-report --name to-date
```

It reads the collection as the owner, keeps a copy under `data/processed/interleaving/`, and writes `eval/results/interleaving/to-date/summary.json`: searches, searches with clicks, clicks and wins by ranking, ties, and the sign test's p-value on the decided searches. Report the counts as illustrative unless there are enough decided searches for the test to mean something.

## Check it by hand

A search through the private API, with the owner's identity token, and a click on its second result:

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "3M PFAS liabilities"}' "$API_URL/v1/search" | jq '{search_id, results: [.results[].label]}'
```

A check's search is a real search: delete its document from `interleaving` afterwards, or the report counts it.
