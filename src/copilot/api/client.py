"""The API from Python, for the web UI and the MCP server: questions streamed as server-sent
events, feedback, cited pages and readiness (ADR-0020).

`parse_sse` reads a stream's lines into events, skipping the keep-alive comments; a refused
question (a 429 over a quota, a 422 for a malformed one) becomes an `error` event, so a
caller handles every outcome the same way. `STEPS` names each step of a run for the people
watching it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

ASK_TIMEOUT_S = 300.0  # an answer, a revision and a slow quota retry fit well within it
BRIEF_TIMEOUT_S = 600.0  # a brief's sections, each an answer of its own
STEPS = {
    "rewrite": "Reading the conversation",
    "understand": "Finding the companies and years",
    "route": "Choosing who answers",
    "doc": "Reading the filings",
    "data": "Querying the facts database",
    "hybrid": "Combining figures and filings",
    "smalltalk": "Replying",
    "decline": "Declining",
    "brief": "Planning and writing the brief's sections",
    "synthesise": "Assembling the answer",
    "validate": "Checking every cited sentence",
    "revise": "Revising unsupported sentences",
    "respond": "Writing the reply",
    "remember": "Finishing",
}


@dataclass(frozen=True, slots=True)
class Event:
    """One server-sent event: its name and its JSON data."""

    kind: str
    data: dict[str, Any]


def parse_sse(lines: Iterable[str]) -> Iterator[Event]:
    """Server-sent events from a stream's lines; comments, such as keep-alives, are skipped."""
    kind: str = "message"
    data: list[str] = []
    for line in lines:
        if not line:
            if data:
                yield Event(kind, json.loads("\n".join(data)))
            kind, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            kind = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:") :].removeprefix(" "))
    if data:
        yield Event(kind, json.loads("\n".join(data)))


METADATA_IDENTITY = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
)


def metadata_id_token(audience: str) -> str:
    """A Google ID token for `audience`, from the metadata server of the Cloud Run
    instance this runs on, signed for the service's own account."""
    response = httpx.get(
        METADATA_IDENTITY,
        params={"audience": audience},
        headers={"Metadata-Flavor": "Google"},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.text


def _expiry(token: str) -> float | None:
    """The `exp` claim of a JWT, or None if it can't be read."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        return None


class GoogleIdToken(httpx.Auth):
    """Signs each request with a Google ID token for `audience` (ADR-0031: only the UI's
    and the MCP server's accounts may call the API). A token lasts an hour; a new one is
    fetched five minutes before it expires."""

    def __init__(
        self,
        audience: str,
        fetch: Callable[[str], str] = metadata_id_token,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.audience = audience
        self._fetch = fetch
        self._clock = clock
        self._token: str | None = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def token(self) -> str:
        with self._lock:
            if self._token is None or self._clock() >= self._expires - 300:
                self._token = self._fetch(self.audience)
                self._expires = _expiry(self._token) or self._clock() + 3600
            return self._token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        yield request


def visitor_from_forwarded(headers: Mapping[str, str], fallback: str) -> str:
    """Who is asking, for the API's quotas: on Cloud Run, a hash of the client's address,
    so a new browser session doesn't reset a visitor's quota; elsewhere, `fallback`, the
    session's own id.

    The address is the last entry of `X-Forwarded-For`, the one Google's front end adds;
    entries a client sends come before it. Which entry the front end adds is checked on
    the deployed service (step 8.7).
    """
    forwarded = next((v for k, v in headers.items() if k.lower() == "x-forwarded-for"), "")
    address = forwarded.split(",")[-1].strip()
    if not address:
        return fallback
    return hashlib.sha256(address.encode()).hexdigest()[:32]


class CopilotClient:
    """The API at `base_url`, as one visitor: the visitor's id goes with every question.

    `id_token=True` signs every call with a Google ID token for `base_url`, as the
    deployment's private API requires.
    """

    def __init__(
        self,
        base_url: str,
        visitor_id: str,
        transport: httpx.BaseTransport | None = None,
        *,
        id_token: bool = False,
        auth: httpx.Auth | None = None,
    ) -> None:
        self.visitor_id = visitor_id
        signer = auth or (GoogleIdToken(base_url.rstrip("/")) if id_token else None)
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=30.0, auth=signer)

    def ask(
        self, question: str, thread_id: str | None = None, *, brief: bool = False
    ) -> Iterator[Event]:
        """The answer's events as they arrive; a refused question is one `error` event.

        `brief=True` asks `/v1/brief` for a research brief on the request instead.
        """
        body: dict[str, Any] = {"question": question}
        if thread_id:
            body["thread_id"] = thread_id
        headers = {"X-Visitor-ID": self.visitor_id}
        path, timeout = ("/v1/brief", BRIEF_TIMEOUT_S) if brief else ("/v1/ask", ASK_TIMEOUT_S)
        try:
            with self._http.stream(
                "POST", path, json=body, headers=headers, timeout=timeout
            ) as response:
                if response.status_code != 200:
                    response.read()
                    yield Event("error", _refusal(response))
                    return
                yield from parse_sse(response.iter_lines())
        except httpx.HTTPError as exc:
            yield Event("error", {"error": f"The copilot can't be reached: {type(exc).__name__}."})

    def feedback(
        self, thread_id: str, turn: int, rating: str, request_id: str | None = None
    ) -> bool:
        """Keep a thumbs up or down on one answer; whether it was kept."""
        body = {"thread_id": thread_id, "turn": turn, "rating": rating, "request_id": request_id}
        try:
            return self._http.post("/v1/feedback", json=body).status_code == 201
        except httpx.HTTPError:
            return False

    def source(self, doc_name: str, page: int) -> dict[str, Any] | None:
        """A cited page's label, section and text, or None when it can't be had."""
        try:
            response = self._http.get(f"/v1/sources/{doc_name}/{page}")
        except httpx.HTTPError:
            return None
        found: dict[str, Any] = response.json() if response.status_code == 200 else {}
        return found or None

    def ready(self) -> dict[str, Any]:
        """The API's readiness checks, or why it couldn't be asked."""
        try:
            checked: dict[str, Any] = self._http.get("/readyz", timeout=5.0).json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"ready": False, "checks": {}, "error": type(exc).__name__}
        return checked


def _refusal(response: httpx.Response) -> dict[str, Any]:
    """A refused question as an error event's data, with the API's reason."""
    try:
        detail = response.json().get("detail", "")
    except ValueError:
        detail = ""
    if response.status_code == 429:
        reason = detail or "Today's quota of questions is used up."
        return {"error": reason, "retry_after": response.headers.get("retry-after")}
    if response.status_code == 422:
        return {"error": "The question couldn't be accepted: it may be empty or too long."}
    return {"error": f"The copilot answered with HTTP {response.status_code}."}
