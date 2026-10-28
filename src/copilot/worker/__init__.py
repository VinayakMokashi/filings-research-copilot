"""The ingestion worker: one filing indexed per Pub/Sub message (ADR-0031).

`copilot.worker.ingest` does the work; `copilot.worker.app` is the Cloud Run service that
Pub/Sub pushes each request to.
"""
