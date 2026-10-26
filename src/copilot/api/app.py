"""The FastAPI application (step 6.1, ADR-0020).

- `POST /v1/ask` answers one question as a stream of server-sent events: `meta` first (the
  request's id and the conversation's), then the graph's own events as they happen
  (`start` and `end` for every node, `event` for what a node reports, `error` if the run
  failed, `response` with the reply), and `done` last. Give the `thread_id` again to ask
  a follow-up.
- `POST /v1/feedback` keeps a thumbs up or down, and an optional comment, on one answer.
- `GET /v1/sources/{doc_name}/{page}` returns a cited filing page: its label, section and
  text.
- `GET /healthz` says the process is up; `GET /readyz` checks what a question needs (the
  facts database, the parsed pages, Qdrant, the model key and, when used, Postgres).

Every response carries an `X-Request-ID`: the caller's, when it sends a valid one, or a new
one. One copilot run happens at a time in a process (see `copilot.api.services`); a
question that waits more than two minutes for its turn gets a busy error instead.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from copilot import __version__
from copilot.api.schemas import (
    AskRequest,
    FeedbackReceipt,
    FeedbackRequest,
    Health,
    Readiness,
    SourcePage,
)
from copilot.api.services import Feedback, Services, build_services
from copilot.config import Settings, get_settings
from copilot.logs import configure_logging

log = structlog.get_logger(__name__)

BUSY_WAIT_S = 120.0
DOC_NAME = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def create_app(services: Services | None = None, settings: Settings | None = None) -> FastAPI:
    """The application. Given `services`, it uses them instead of building the real ones."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if services is not None:
            app.state.services = services
            yield
            return
        config = settings or get_settings()
        configure_logging(config.log_level, config.log_format)
        with build_services(config) as built:
            app.state.services = built
            yield

    app = FastAPI(
        title="Filings Research Copilot",
        version=__version__,
        summary="Questions about public companies' SEC filings, answered with citations.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_ids(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        given = request.headers.get("x-request-id", "")
        request_id = given if _REQUEST_ID.match(given) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    @app.get("/healthz", tags=["health"])
    def healthz() -> Health:
        """The process is up."""
        return Health()

    @app.get("/readyz", tags=["health"], responses={503: {"model": Readiness}})
    def readyz(request: Request) -> JSONResponse:
        """Whether a question can be answered now: each check, and all of them together."""
        checks = _services(request).checks()
        ready = all(checks.values())
        body = Readiness(ready=ready, checks=checks).model_dump()
        return JSONResponse(body, status_code=200 if ready else 503)

    @app.post("/v1/ask", response_class=EventSourceResponse, tags=["copilot"])
    def ask(body: AskRequest, request: Request) -> Iterator[ServerSentEvent]:
        """Answer one question, streaming the graph's events as server-sent events."""
        services = _services(request)
        request_id: str = request.state.request_id
        thread_id = body.thread_id or uuid.uuid4().hex[:12]
        ids = {"request_id": request_id, "thread_id": thread_id}
        yield ServerSentEvent(event="meta", data=ids)
        if not services.lock.acquire(timeout=BUSY_WAIT_S):
            busy = "The copilot is busy with another question; try again shortly."
            yield ServerSentEvent(event="error", data={"error": busy})
            yield ServerSentEvent(event="done", data=ids)
            return
        try:
            yield from _events(services, body, thread_id, request_id)
        finally:
            services.lock.release()
        yield ServerSentEvent(event="done", data=ids)

    @app.post("/v1/feedback", status_code=201, tags=["copilot"])
    def feedback(body: FeedbackRequest, request: Request) -> FeedbackReceipt:
        """Keep a reader's verdict on one answer."""
        record = Feedback(
            body.thread_id, body.turn, body.rating, body.comment.strip(), body.request_id
        )
        return FeedbackReceipt(id=_services(request).feedback.add(record))

    @app.get(
        "/v1/sources/{doc_name}/{page}", tags=["sources"], responses={404: {"description": "None"}}
    )
    def source(
        request: Request,
        doc_name: Annotated[str, PathParam(pattern=DOC_NAME)],
        page: Annotated[int, PathParam(ge=0)],
    ) -> SourcePage:
        """A filing page as an answer cites it: 0-based, so PDF page 60 is page 59."""
        found = _services(request).page(doc_name, page)
        if found is None:
            raise HTTPException(status_code=404, detail="No such page.")
        parsed, label = found
        return SourcePage(
            doc_name=doc_name, page=page, label=label, section=parsed.section, text=parsed.text
        )

    return app


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


def _events(
    services: Services, body: AskRequest, thread_id: str, request_id: str
) -> Iterator[ServerSentEvent]:
    """The run's events as server-sent events; a failure ends the stream with an error."""
    sent_error = False
    try:
        events = services.copilot.stream(body.question, thread_id=thread_id, user_id=body.user_id)
        for number, item in enumerate(events, start=1):
            sent_error = sent_error or item.get("type") == "error"
            yield ServerSentEvent(event=str(item.get("type", "event")), data=item, id=str(number))
    except Exception:
        log.exception("api.ask_failed", request_id=request_id, thread=thread_id)
        if not sent_error:  # the runner sends its own error event when the graph fails
            yield ServerSentEvent(event="error", data={"error": "The copilot failed."})
