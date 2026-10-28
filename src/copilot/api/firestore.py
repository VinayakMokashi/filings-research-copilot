"""The API's state in Firestore, for the deployment on Google Cloud (ADR-0031).

Quotas, cached answers and feedback must outlive an instance and be the same for every
instance. On Cloud Run an instance stops when idle, so memory forgets them, and Cloud SQL
runs only during demo windows. Firestore is always on, shared, and free at this volume.
Conversations stay in memory (one API instance), since visitors keep no notes.

- **Quotas** are two counters a day, one per visitor and one for everyone, raised
  together in a batch. The check and the increment happen under the store's lock, which
  serialises them within an instance. With more than one instance, a few questions could
  slip past a limit at the same moment, which the daily budget tolerates.
- **Cached answers** are stored as JSON text, since Firestore can't hold the lists of
  rows inside lists that a data answer carries. Each has an `expires_at`, and a TTL
  policy deletes it after that.
- **Feedback** is one document per rating, for Phase 9's preference pairs.

Every document has an `expires_at` except feedback, so nothing else accumulates.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from copilot.api.cache import Cached, normalise_question
from copilot.api.quotas import Verdict


class Firestore(Protocol):
    """What these stores use of `google.cloud.firestore.Client`."""

    def collection(self, name: str) -> Any: ...
    def batch(self) -> Any: ...


def firestore_client(project: str | None = None) -> Firestore:
    """A Firestore client with the environment's credentials (on Cloud Run, the service's
    own account)."""
    from google.cloud import firestore

    return firestore.Client(project=project)


def _increment(by: int) -> Any:
    from google.cloud import firestore

    return firestore.Increment(by)


def _count(snapshot: Any) -> int:
    data = snapshot.to_dict() if snapshot.exists else None
    return int((data or {}).get("questions", 0))


class FirestoreQuotas:
    """Daily quotas in Firestore: `quotas/<day>` for everyone, `quotas/<day>/visitors/<id>`
    for each visitor."""

    def __init__(self, client: Firestore) -> None:
        self.client = client
        self._lock = threading.Lock()

    def take(self, visitor: str, day: date, per_visitor: int, total: int) -> Verdict:
        everyone_doc = self.client.collection("quotas").document(day.isoformat())
        mine_doc = everyone_doc.collection("visitors").document(visitor)
        with self._lock:
            if _count(mine_doc.get()) >= per_visitor:
                return Verdict(False, "visitor")
            if _count(everyone_doc.get()) >= total:
                return Verdict(False, "total")
            # Kept two days past their day, then deleted by the TTL policy.
            expires = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=3)
            batch = self.client.batch()
            for doc in (everyone_doc, mine_doc):
                batch.set(doc, {"questions": _increment(1), "expires_at": expires}, merge=True)
            batch.commit()
            return Verdict(True)


def _answer_id(question: str) -> str:
    """A document ID for a question: the hash of its normalised form."""
    return hashlib.sha256(normalise_question(question).encode()).hexdigest()


class FirestoreCache:
    """Answers to repeated questions, in `answers/<hash of the question>`."""

    def __init__(self, client: Firestore, ttl: timedelta) -> None:
        self.client = client
        self.ttl = ttl

    def get(self, question: str, now: datetime) -> Cached | None:
        snapshot = self.client.collection("answers").document(_answer_id(question)).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        created = data["created"]
        if now - created >= self.ttl:
            return None  # expired; the TTL policy removes it within a day
        return Cached(str(data["question"]), json.loads(data["response"]), created)

    def put(self, question: str, response: dict[str, Any], now: datetime) -> None:
        self.client.collection("answers").document(_answer_id(question)).set(
            {
                "question": question,
                "response": json.dumps(response, ensure_ascii=False, default=str),
                "created": now,
                "expires_at": now + self.ttl,
            }
        )


class FirestoreFeedback:
    """Feedback in `feedback/<id>`; returns how many ratings this instance has stored."""

    def __init__(self, client: Firestore) -> None:
        self.client = client
        self._lock = threading.Lock()
        self._stored = 0

    def add(self, feedback: Any) -> int:
        self.client.collection("feedback").document().set(
            {
                "created": datetime.now(UTC),
                "thread_id": feedback.thread_id,
                "turn": feedback.turn,
                "rating": feedback.rating,
                "comment": feedback.comment,
                "request_id": feedback.request_id,
            }
        )
        with self._lock:
            self._stored += 1
            return self._stored
