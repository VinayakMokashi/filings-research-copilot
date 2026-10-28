"""The ingestion worker's HTTP service: Pub/Sub pushes each request here (ADR-0031).

Pub/Sub delivers a message as a POST with a JSON envelope whose `message.data` is the
request, base64-encoded. Cloud Run checks the push's signed token before the request
arrives, since only Pub/Sub's push account may call this service. The status code is
the acknowledgement:

- **204** acknowledges: the filing is indexed, or was already.
- **400** for a request that can't be read. Pub/Sub retries it, then after five attempts
  moves it to the dead-letter topic, where an alert shows it.
- **500** for a failure on the way (a download, the parser, Qdrant). Pub/Sub retries it
  with backoff.

Serve it with `uvicorn copilot.worker.app:create_app --factory`.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Request, Response
from pydantic import ValidationError

from copilot.api.schemas import Health
from copilot.config import Settings, get_settings
from copilot.ingest.jobs import JobResult
from copilot.logs import configure_logging, get_logger
from copilot.worker.ingest import Ingester, IngestRequest

log = get_logger(__name__)


def read_request(envelope: Any) -> IngestRequest:
    """The request inside a Pub/Sub push envelope; ValueError if it can't be read."""
    try:
        data = base64.b64decode(envelope["message"]["data"], validate=True)
        return IngestRequest.model_validate(json.loads(data))
    except (KeyError, TypeError, binascii.Error, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"unreadable ingestion request: {type(exc).__name__}") from exc


def create_app(
    handler: Callable[[IngestRequest], JobResult] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """The service; `handler` replaces the real ingester (for tests)."""
    config = settings or get_settings()
    configure_logging(config.log_level, config.log_format)
    app = FastAPI(title="Filings Research Copilot: ingestion worker")
    ingest: Callable[[IngestRequest], JobResult] | None = handler

    @app.get("/healthz")
    def healthz() -> Health:
        return Health(commit=config.git_sha)

    @app.post("/pubsub/ingest", status_code=204)
    async def pubsub_ingest(request: Request) -> Response:
        nonlocal ingest
        try:
            envelope = await request.json()
            job = read_request(envelope)
        except ValueError as exc:  # also the body's own JSONDecodeError
            log.warning("ingest.bad_request", error=str(exc))
            return Response(status_code=400)
        if ingest is None:
            ingest = Ingester(config)
        try:
            result = ingest(job)
        except Exception as exc:  # retried by Pub/Sub, then dead-lettered
            log.error("ingest.failed", doc=job.doc_name, error=f"{type(exc).__name__}: {exc}")
            return Response(status_code=500)
        log.info("ingest.done", **asdict(result))
        return Response(status_code=204)

    return app
