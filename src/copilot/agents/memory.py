"""Memory: follow-ups made standalone, and short notes kept about a user (step 5.5).

Two kinds of memory serve a conversation:

- **Within a conversation** the checkpointer keeps every turn (ADR-0018). A follow-up such
  as "And in 2019?" only makes sense with the turn before it, so `rewrite_followup` turns
  it into a standalone question from the last few turns before anything else runs; the
  router, the agents and the validator then see one clear question. A first question,
  from a user with no notes, needs no call.
- **Across conversations** a store keeps short notes about the user, in the style of Mem0
  (Chhikara et al., 2025). After each turn, `extract` asks a model for facts worth keeping
  (the companies the user follows, how they like figures given, their role), and
  `reconcile` compares them with the stored notes and decides, for each, to add a note,
  update one, delete one it contradicts, or do nothing. The notes help the next
  conversation's rewrite: "How did they do last year?" can be read with "Follows Netflix".

Rewriting runs on the `strong` role, since a wrong reading misleads every later step; the
notes run on the `small` role, two short calls a turn.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from copilot.llm import LLMClient, Message, ModelRole, system, user
from copilot.llm.parsing import json_object

MAX_TURNS = 3  # enough to resolve "those" and "and in 2019?", short enough to keep old topics out
REWRITE_ROLE: ModelRole = "strong"
NOTES_ROLE: ModelRole = "small"
PROMPT_VERSION = "1"

REWRITE_SYSTEM = (
    "You rewrite the latest question a user asks a research assistant about company filings "
    "into a question that stands on its own. You never answer it. You reply with JSON only."
)
REWRITE_INSTRUCTION = """\
If the new question depends on the conversation or on what you know about the user (for \
example "And in 2019?", "What about its debt?", "How did my companies do last year?"), \
rewrite it as one standalone question that names the company, the measure and the period \
it inherits. If it already stands alone, return it unchanged.

Reply with JSON only: {"standalone": "the question"}"""

EXTRACT_SYSTEM = """\
You keep short notes about a user of a research assistant for company filings, so that \
later conversations go better. From the exchange below, note the facts about the user \
worth keeping: the companies they follow or care about, how they like answers given \
(units, length, detail), and their role or purpose, if they say. Each note is one short \
sentence about the user, such as "Follows Netflix." Don't note what was asked or answered, \
and don't guess.

Reply with JSON only: {"facts": ["...", ...]}, with an empty list when nothing is worth \
keeping."""

RECONCILE_SYSTEM = """\
You keep a short list of notes about a user. Compare the new facts with the current \
notes, and decide what to do with each fact:
- "add" it as a new note;
- "update" a note (give its id and the new text) when the fact refines or changes it;
- "delete" a note (give its id) when the fact shows it is no longer true;
- "none" when a note already says it.

Reply with JSON only: {"operations": [{"action": "add", "update", "delete" or "none", \
"id": "the note's id, for update and delete", "text": "the note, for add and update"}]}"""


@dataclass(frozen=True, slots=True)
class Note:
    """One fact about the user, as the store keeps it."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class Rewrite:
    standalone: str
    rewritten: bool
    error: str | None = None


class _Standalone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    standalone: str


class _Facts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facts: list[str] = Field(default_factory=list)


class Operation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["add", "update", "delete", "none"]
    id: str = ""
    text: str = ""


class _Operations(BaseModel):
    model_config = ConfigDict(extra="ignore")

    operations: list[Operation] = Field(default_factory=list)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def rewrite_messages(
    turns: Sequence[tuple[str, str]], question: str, notes: Sequence[str]
) -> list[Message]:
    lines = [
        f"Q{n}: {asked}\nA{n}: {_clip(answer, 300)}" for n, (asked, answer) in enumerate(turns, 1)
    ]
    known = "\n".join(f"- {note}" for note in notes) or "(nothing yet)"
    conversation = "\n\n".join(lines) or "(this is the first question)"
    prompt = (
        f"Conversation so far (oldest first):\n{conversation}\n\nWhat you know about the "
        f"user:\n{known}\n\nNew question: {question}\n\n{REWRITE_INSTRUCTION}"
    )
    return [system(REWRITE_SYSTEM), user(prompt)]


def rewrite_followup(
    llm: LLMClient, turns: Sequence[tuple[str, str]], question: str, notes: Sequence[str] = ()
) -> Rewrite:
    """`question` as a standalone question, given the last turns (question, answer) and notes.

    Without turns or notes there is nothing to resolve and no call is made; a reply that
    can't be read keeps the question as it was.
    """
    if not turns and not notes:
        return Rewrite(question, rewritten=False)
    response = llm.complete(
        rewrite_messages(turns[-MAX_TURNS:], question, notes),
        role=REWRITE_ROLE,
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    try:
        standalone = " ".join(
            _Standalone.model_validate(json_object(response.text)).standalone.split()
        )
    except (ValueError, ValidationError) as exc:
        return Rewrite(question, rewritten=False, error=str(exc)[:300])
    if not standalone:
        return Rewrite(question, rewritten=False, error="an empty rewrite")
    return Rewrite(standalone, rewritten=standalone != question)


def extract(llm: LLMClient, question: str, answer: str) -> list[str]:
    """Facts about the user worth keeping, from one exchange."""
    exchange = f"User: {question}\nAssistant: {_clip(answer, 600)}"
    response = llm.complete(
        [system(EXTRACT_SYSTEM), user(exchange)],
        role=NOTES_ROLE,
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    try:
        facts = _Facts.model_validate(json_object(response.text)).facts
    except (ValueError, ValidationError):
        return []
    return [" ".join(fact.split()) for fact in facts if fact.strip()]


def reconcile(llm: LLMClient, notes: Sequence[Note], facts: Sequence[str]) -> list[Operation]:
    """What to do with each new fact, given the current notes."""
    if not facts:
        return []
    current = "\n".join(f"- id {note.id}: {note.text}" for note in notes) or "(none)"
    new = "\n".join(f"- {fact}" for fact in facts)
    response = llm.complete(
        [system(RECONCILE_SYSTEM), user(f"Current notes:\n{current}\n\nNew facts:\n{new}")],
        role=NOTES_ROLE,
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    try:
        return _Operations.model_validate(json_object(response.text)).operations
    except (ValueError, ValidationError):
        return []


# ---------------------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------------------


def namespace(user_id: str) -> tuple[str, ...]:
    return ("notes", user_id)


def recall(store: BaseStore, user_id: str, limit: int = 50) -> list[Note]:
    """The user's notes, oldest first."""
    items = store.search(namespace(user_id), limit=limit)
    ordered = sorted(items, key=lambda item: item.created_at)
    return [Note(item.key, str(item.value.get("text", ""))) for item in ordered]


def apply(store: BaseStore, user_id: str, operations: Sequence[Operation]) -> dict[str, int]:
    """Carry out the operations on the user's notes; returns how many of each were done.

    An update or delete that names an unknown note is skipped, never guessed.
    """
    known = {note.id for note in recall(store, user_id)}
    done = dict.fromkeys(("add", "update", "delete"), 0)
    for operation in operations:
        text = " ".join(operation.text.split())
        if operation.action == "add" and text:
            store.put(namespace(user_id), uuid.uuid4().hex[:8], {"text": text})
            done["add"] += 1
        elif operation.action == "update" and operation.id in known and text:
            store.put(namespace(user_id), operation.id, {"text": text})
            done["update"] += 1
        elif operation.action == "delete" and operation.id in known:
            store.delete(namespace(user_id), operation.id)
            known.discard(operation.id)
            done["delete"] += 1
    return done
