"""Load test of the deployed API, without spending model quota (step 8.7).

Before the load starts, each question below is asked once, so its answer is in the
answer cache (Firestore). Those few calls are the only ones that reach a model. The
simulated visitors then send the same questions again, which the API serves from the
cache, with each visitor's own id. A cached answer costs no quota. They also read cited
pages and check health, so the test measures Cloud Run, Firestore and the API's own
code, not the models.

The API is private, so each request carries an ID token. A project owner's gcloud
login can mint one, and it lasts an hour:

    export LOAD_TEST_TOKEN="$(gcloud auth print-identity-token)"
    uvx locust -f loadtest/locustfile.py --host https://api-<project number>.asia-south1.run.app \\
        --users 20 --spawn-rate 2 --run-time 5m --headless --csv dist/load-test

The questions are the web UI's examples and two of the SQL set's, all the project's own.
"""

from __future__ import annotations

import os
import random
import uuid
from typing import Any

from locust import HttpUser, between, events, task

QUESTIONS = (
    "What was 3M's capital expenditure in 2018?",
    "How did Boeing's revenue change from 2019 to 2022, and what drove the recovery?",
    "What risks does Netflix name in its 2022 10-K?",
    "Which companies do you cover?",
    "What was Microsoft's revenue in fiscal 2022, in billions of dollars?",
    "What were Coca-Cola's total assets at the end of 2022?",
)
# Cited pages to read: (document, 0-based page).
PAGES = (("3M_2018_10K", 46), ("BOEING_2022_10K", 30), ("COCACOLA_2022_10K", 60))


def _headers(visitor: str) -> dict[str, str]:
    token = os.environ.get("LOAD_TEST_TOKEN", "")
    headers = {"X-Visitor-ID": visitor, "Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _ask(client: Any, question: str, visitor: str, name: str) -> tuple[bool, bool]:
    """Ask once and read the whole stream; returns (answered, served from the cache)."""
    with client.post(
        "/v1/ask",
        json={"question": question},
        headers=_headers(visitor),
        stream=True,
        catch_response=True,
        name=name,
    ) as response:
        if response.status_code != 200:
            response.failure(f"status {response.status_code}")
            return False, False
        text = "".join(chunk.decode("utf-8", "replace") for chunk in response.iter_content(4096))
        if "event: done" not in text:
            response.failure("the stream ended without its done event")
            return False, False
        if "event: error" in text:  # the API was busy, or a run failed
            response.failure("the stream carried an error event")
            return False, False
        response.success()
        return True, '"cached": true' in text or '"cached":true' in text


@events.test_start.add_listener
def warm_the_cache(environment: Any, **kwargs: Any) -> None:
    """Ask every question once, so the load is served from the answer cache."""
    from locust.clients import HttpSession

    session = HttpSession(
        base_url=environment.host, request_event=environment.events.request, user=None
    )
    for question in QUESTIONS:
        answered, cached = _ask(session, question, f"warm-{uuid.uuid4().hex[:12]}", "warm-up")
        state = "cached already" if cached else ("answered" if answered else "FAILED")
        print(f"warm-up: {state}: {question}")


class Visitor(HttpUser):
    """Someone using the copilot: mostly repeated questions, some cited pages."""

    wait_time = between(2, 8)

    def on_start(self) -> None:
        self.visitor = f"load-{uuid.uuid4().hex[:16]}"

    @task(6)
    def ask_a_cached_question(self) -> None:
        _ask(self.client, random.choice(QUESTIONS), self.visitor, "/v1/ask (cached)")

    @task(3)
    def read_a_cited_page(self) -> None:
        doc, page = random.choice(PAGES)
        self.client.get(
            f"/v1/sources/{doc}/{page}",
            headers=_headers(self.visitor),
            name="/v1/sources/[doc]/[page]",
        )

    @task(1)
    def check_health(self) -> None:
        self.client.get("/healthz", headers=_headers(self.visitor))
