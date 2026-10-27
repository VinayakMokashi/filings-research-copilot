"""The FastAPI application (step 6.1, ADR-0020).

- `POST /v1/ask` answers one question as a stream of server-sent events: `meta` first (the
  request's id and the conversation's), then the graph's own events as they happen
  (`start` and `end` for every node, `event` for what a node reports, `error` if the run
  failed, `response` with the reply), and `done` last. Give the `thread_id` again to ask
  a follow-up.
- `POST /v1/brief` writes a research brief (step 7.6) for the request in `question`,
  streamed the same way: the brief crew's plan, sections and edit arrive as `event`s, and
  the `response` holds the brief as Markdown, its citations and its sections.
- `POST /v1/feedback` keeps a thumbs up or down, and an optional comment, on one answer.
- `GET /v1/sources/{doc_name}/{page}` returns a cited filing page: its label, section and
  text.
- `GET /healthz` says the process is up; `GET /readyz` checks what a question needs (the
  facts database, the parsed pages, Qdrant, the model key and, when used, Postgres).

Every response carries an `X-Request-ID`: the caller's, when it sends a valid one, or a new
one. One copilot run happens at a time in a process (see `copilot.api.services`); a
question that waits more than two minutes for its turn gets a busy error instead.

Guardrails (step 6.2): a question counts against daily quotas, per visitor and in total,
and one over either gets a 429 with `Retry-After` before any model call
(`copilot.api.quotas`), unless it repeats a question an anonymous caller asked in a
new conversation, which gets the stored answer with no run and no quota
(`copilot.api.cache`); briefs are stored apart from answers, so the same words asked as a
question and as a brief never share a reply. A caller who gives no `user_id` is
anonymous: nothing is noted about them, so one visitor's notes never shape another's
answers.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from copilot import __version__
from copilot.agents.graph import Turn
from copilot.agents.memory import ANONYMOUS
from copilot.agents.router import Route
from copilot.api.cache import Cached, age_seconds, reusable
from copilot.api.quotas import seconds_until_reset, visitor_key
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
BRIEF_KEY = "[brief] "  # what a brief's request is stored under in the answer cache
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

    @app.post(
        "/v1/ask",
        response_class=EventSourceResponse,
        tags=["copilot"],
        responses={429: {"description": "A daily quota is used up; see Retry-After."}},
    )
    def ask(
        body: AskRequest, request: Request, cached: Annotated[Cached | None, Depends(admit)]
    ) -> Iterator[ServerSentEvent]:
        """Answer one question, streaming the graph's events as server-sent events."""
        yield from _run(body, request, cached, key=body.question)

    @app.post(
        "/v1/brief",
        response_class=EventSourceResponse,
        tags=["copilot"],
        responses={429: {"description": "A daily quota is used up; see Retry-After."}},
    )
    def brief(
        body: AskRequest,
        request: Request,
        cached: Annotated[Cached | None, Depends(admit_brief)],
    ) -> Iterator[ServerSentEvent]:
        """Write a research brief for the request in `question`, streaming the crew's steps."""
        yield from _run(body, request, cached, key=BRIEF_KEY + body.question, route="brief")

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


def admit(request: Request, body: AskRequest) -> Cached | None:
    """A stored answer to a repeated question, which costs no quota; otherwise the question
    is counted against today's quotas, or refused with a 429.

    It takes the validated body, so a malformed request is refused first and counts for
    nothing.
    """
    return _admit(request, body, body.question)


def admit_brief(request: Request, body: AskRequest) -> Cached | None:
    """As `admit`, for a brief: its stored reply is kept apart from answers."""
    return _admit(request, body, BRIEF_KEY + body.question)


def _admit(request: Request, body: AskRequest, key: str) -> Cached | None:
    services = _services(request)
    now = datetime.now(UTC)
    if services.cache is not None and cacheable(body):
        stored = services.cache.get(key, now)
        if stored is not None:
            return stored
    take_quota(services, request, now)
    return None


def _run(
    body: AskRequest,
    request: Request,
    cached: Cached | None,
    *,
    key: str,
    route: Route | None = None,
) -> Iterator[ServerSentEvent]:
    """One run's stream: `meta`, a stored reply or the graph's events, then `done`."""
    services = _services(request)
    request_id: str = request.state.request_id
    thread_id = body.thread_id or uuid.uuid4().hex[:12]
    user_id = body.user_id or f"{ANONYMOUS}{thread_id}"
    ids = {"request_id": request_id, "thread_id": thread_id}
    yield ServerSentEvent(event="meta", data=ids)
    if cached is not None:
        yield from _replay(services, body.question, cached, thread_id)
        yield ServerSentEvent(event="done", data=ids)
        return
    if not services.lock.acquire(timeout=BUSY_WAIT_S):
        busy = "The copilot is busy with another question; try again shortly."
        yield ServerSentEvent(event="error", data={"error": busy})
        yield ServerSentEvent(event="done", data=ids)
        return
    seen: dict[str, Any] = {}
    try:
        yield from _events(services, body.question, thread_id, user_id, request_id, seen, route)
    finally:
        services.lock.release()
    response = seen.get("response")
    if services.cache is not None and cacheable(body) and response and reusable(response):
        services.cache.put(key, response, datetime.now(UTC))
    yield ServerSentEvent(event="done", data=ids)


def cacheable(body: AskRequest) -> bool:
    """A new conversation from an anonymous caller: its answer depends on the question alone."""
    return body.thread_id is None and body.user_id is None


def take_quota(services: Services, request: Request, now: datetime) -> None:
    """Count the question against today's quotas, or refuse it with a 429."""
    verdict = services.quotas.take(
        visitor_key(request), now.date(), services.per_visitor, services.total
    )
    if not verdict.allowed:
        whose = "your" if verdict.over == "visitor" else "everyone's"
        raise HTTPException(
            status_code=429,
            detail=f"Today's quota of questions ({whose}) is used up; it resets at midnight UTC.",
            headers={"Retry-After": str(seconds_until_reset(now))},
        )


def _replay(
    services: Services, question: str, cached: Cached, thread_id: str
) -> Iterator[ServerSentEvent]:
    """A stored answer as events, added to the conversation so a follow-up can build on it."""
    now = datetime.now(UTC)
    hit = {"type": "event", "event": "cache", "question": cached.question}
    yield ServerSentEvent(event="event", data=hit | {"age_s": age_seconds(cached, now)}, id="1")
    stored = cached.response
    turn: Turn = {
        "question": question,
        "standalone": str(stored.get("standalone") or question),
        "route": str(stored.get("route", "")),
        "answer": str(stored.get("text", "")),
    }
    try:
        services.copilot.record(thread_id, turn)
    except Exception:
        log.exception("api.record_failed", thread=thread_id)
    response = stored | {"type": "response", "thread": thread_id, "turn": 1, "cached": True}
    yield ServerSentEvent(event="response", data=response, id="2")


def _events(
    services: Services,
    question: str,
    thread_id: str,
    user_id: str,
    request_id: str,
    seen: dict[str, Any],
    route: Route | None = None,
) -> Iterator[ServerSentEvent]:
    """The run's events as server-sent events; a failure ends the stream with an error.

    The response, when one comes, is also left in `seen` under `response`.
    """
    sent_error = False
    try:
        events = services.copilot.stream(
            question, thread_id=thread_id, user_id=user_id, route=route
        )
        for number, item in enumerate(events, start=1):
            sent_error = sent_error or item.get("type") == "error"
            if item.get("type") == "response":
                seen["response"] = item
            yield ServerSentEvent(event=str(item.get("type", "event")), data=item, id=str(number))
    except Exception:
        log.exception("api.ask_failed", request_id=request_id, thread=thread_id)
        if not sent_error:  # the runner sends its own error event when the graph fails
            yield ServerSentEvent(event="error", data={"error": "The copilot failed."})
