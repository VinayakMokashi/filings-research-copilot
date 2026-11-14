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
- **Paid-fallback spend** (ADR-0033) is one more counter in the day's quota document,
  so it expires with it, and so is the answer bandit's (ADR-0036), `bandit_usd`.
- **Feedback** is one document per rating, with the exchange it rates as JSON text
  (ADR-0035), and **preferences** one per visitor's pick between two answers.
- **The answer bandit** keeps each arm's count and reward sum in `bandit/answer-arms`,
  raised with atomic increments, and one document per answer it paid for in
  `bandit-answers`, with the rewards as they come.

Feedback, preferences and the bandit's records are kept; every other document has an
`expires_at`, so nothing else accumulates.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from copilot.answer.bandit import ARMS
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


def _increment(by: float) -> Any:
    from google.cloud import firestore

    return firestore.Increment(by)


def _count(snapshot: Any) -> int:
    data = snapshot.to_dict() if snapshot.exists else None
    return int((data or {}).get("questions", 0))


def _quota_expiry(day: date) -> datetime:
    """Two days past the day; the TTL policy then deletes the document."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=3)


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
            expires = _quota_expiry(day)
            batch = self.client.batch()
            for doc in (everyone_doc, mine_doc):
                batch.set(doc, {"questions": _increment(1), "expires_at": expires}, merge=True)
            batch.commit()
            return Verdict(True)


class FirestoreSpend:
    """A day's spend in `quotas/<day>`: the paid fallback's as `paid_usd`, or another
    counter's, such as the answer bandit's `bandit_usd`."""

    def __init__(self, client: Firestore, field: str = "paid_usd") -> None:
        self.client = client
        self.field = field

    def spent(self, day: date) -> float:
        snapshot = self.client.collection("quotas").document(day.isoformat()).get()
        data = snapshot.to_dict() if snapshot.exists else None
        return float((data or {}).get(self.field, 0.0))

    def add(self, day: date, usd: float) -> None:
        self.client.collection("quotas").document(day.isoformat()).set(
            {self.field: _increment(usd), "expires_at": _quota_expiry(day)}, merge=True
        )


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


def _json(value: Any) -> str | None:
    """Nested lists (a source's rows, a model's tokens) as Firestore can't hold them: text."""
    return None if value is None else json.dumps(value, ensure_ascii=False, default=str)


class FirestoreFeedback:
    """Feedback in `feedback/<id>`, each rating with the exchange it rates (or none, when
    the API no longer held it); returns how many ratings this instance has stored."""

    def __init__(self, client: Firestore) -> None:
        self.client = client
        self._lock = threading.Lock()
        self._stored = 0

    def add(self, feedback: Any, exchange: dict[str, Any] | None = None) -> int:
        self.client.collection("feedback").document().set(
            {
                "created": datetime.now(UTC),
                "thread_id": feedback.thread_id,
                "turn": feedback.turn,
                "rating": feedback.rating,
                "comment": feedback.comment,
                "request_id": feedback.request_id,
                "exchange": _json(exchange),
            }
        )
        with self._lock:
            self._stored += 1
            return self._stored


class FirestorePreferences:
    """A visitor's pick between two answers to one question in `preferences/<id>`, with
    both exchanges; returns how many this instance has stored."""

    def __init__(self, client: Firestore) -> None:
        self.client = client
        self._lock = threading.Lock()
        self._stored = 0

    def add(self, preference: Any) -> int:
        self.client.collection("preferences").document().set(
            {
                "created": datetime.now(UTC),
                "chosen": preference.chosen,
                "comment": preference.comment,
                "first": _json(preference.first),
                "second": _json(preference.second),
            }
        )
        with self._lock:
            self._stored += 1
            return self._stored


def _field(arm: str) -> str:
    return arm.replace("-", "_")


class FirestoreArmStats:
    """Each arm's count of rewards and their sum, as `count_<arm>` and `sum_<arm>` in
    `bandit/answer-arms`. Increments are atomic, so no transaction is needed."""

    def __init__(self, client: Firestore) -> None:
        self.document = client.collection("bandit").document("answer-arms")

    def read(self) -> tuple[dict[str, int], dict[str, float]]:
        snapshot = self.document.get()
        data = (snapshot.to_dict() if snapshot.exists else None) or {}
        counts = {arm: int(data.get(f"count_{_field(arm)}", 0)) for arm in ARMS}
        sums = {arm: float(data.get(f"sum_{_field(arm)}", 0.0)) for arm in ARMS}
        return counts, sums

    def add(self, arm: str, value: float) -> None:
        self.document.set(
            {
                f"count_{_field(arm)}": _increment(1),
                f"sum_{_field(arm)}": _increment(value),
                "updated": datetime.now(UTC),
            },
            merge=True,
        )


class FirestoreBanditLog:
    """One document per answer the bandit paid for, `bandit-answers/<request id>`, with its
    rewards merged in as they come."""

    def __init__(self, client: Firestore) -> None:
        self.collection = client.collection("bandit-answers")

    def start(self, request_id: str, record: dict[str, Any]) -> None:
        self.collection.document(request_id).set(record)

    def update(self, request_id: str, fields: dict[str, Any]) -> None:
        self.collection.document(request_id).set(fields, merge=True)
