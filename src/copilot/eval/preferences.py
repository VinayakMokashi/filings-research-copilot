"""Preference pairs from what readers and the validator chose (step 9.2, ADR-0035).

A pair is one prompt with a chosen and a rejected answer: the input of preference tuning
such as DPO (Rafailov et al., 2023). Each pair is written in TRL's conversational
preference format, and its source, labeller and ids go to a metadata line beside it.

- **The prompt** is the answer prompt the copilot used: its instructions, the numbered
  sources, and the question as read. The doc agent and the hybrid each have their own
  (`copilot.answer.generate`, `copilot.answer.hybrid_v2`). When the two answers were
  written from different sources, or their sources weren't kept (an answer from the
  cache), the prompt is the question alone, and the metadata says so.
- **The answers** are the texts readers saw, after the calculator filled in the figures.

Three sources:

- `retry`: a reader's pick between an answer and its second answer ("neither" makes no
  pair);
- `ratings`: an answer rated up against one rated down, for the same question as read;
- `validator`: the revision that passed the validator's check against the draft that
  failed it, judged by the validator's model, not a person.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from copilot.answer import generate, hybrid_v2
from copilot.answer.context import Source
from copilot.api.cache import normalise_question
from copilot.llm import Message, assistant, user

READER = "a reader"
READERS = "readers' ratings"
VALIDATOR = "the validator's model"
MAX_PAIRS_A_QUESTION = 10  # opposite ratings of one question make at most this many pairs


@dataclass(frozen=True, slots=True)
class Pair:
    prompt: list[Message]
    chosen: str
    rejected: str
    source: str  # retry, ratings or validator
    labeller: str
    ids: tuple[str, ...]  # the request ids, or a run's question id
    prompt_kind: str  # "sources": the answer prompt; "question": the question alone

    def trl(self) -> dict[str, Any]:
        """The pair in TRL's conversational preference format."""
        return {
            "prompt": self.prompt,
            "chosen": [assistant(self.chosen)],
            "rejected": [assistant(self.rejected)],
        }

    def meta(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "labeller": self.labeller,
            "ids": list(self.ids),
            "prompt": self.prompt_kind,
        }


def _sources(exchange: Mapping[str, Any]) -> list[Source]:
    return [
        Source(
            int(source["number"]),
            str(source["doc_name"]),
            int(source["page"]),
            str(source["label"]),
            str(source["text"]),
            0,
        )
        for source in exchange.get("sources") or []
    ]


def _shown(sources: Sequence[Source]) -> list[tuple[int, str, int]]:
    return [(source.number, source.doc_name, source.page) for source in sources]


def prompt_for(
    question: str, kind: str | None, *exchanges: Mapping[str, Any]
) -> tuple[list[Message], str]:
    """The answer prompt behind the exchanges' answers, when they share their sources;
    otherwise the question alone."""
    sources = [_sources(exchange) for exchange in exchanges]
    same = bool(sources[0]) and all(_shown(s) == _shown(sources[0]) for s in sources)
    if same and kind in ("doc", "hybrid"):
        build = generate.answer_messages if kind == "doc" else hybrid_v2.answer_messages
        return build(question, sources[0]), "sources"
    return [user(question)], "question"


def retry_pairs(preferences: Iterable[Mapping[str, Any]]) -> list[Pair]:
    """A pair from each pick of one answer over its second answer, or the other way."""
    pairs = []
    for preference in preferences:
        chosen = preference.get("chosen")
        first, second = preference.get("first") or {}, preference.get("second") or {}
        if chosen not in ("first", "second") or not first or not second:
            continue
        good, bad = (first, second) if chosen == "first" else (second, first)
        if good.get("text") == bad.get("text"):
            continue
        question = str(first.get("standalone") or first.get("question") or "")
        prompt, kind = prompt_for(question, first.get("kind"), good, bad)
        ids = (str(good.get("request_id")), str(bad.get("request_id")))
        pairs.append(Pair(prompt, good["text"], bad["text"], "retry", READER, ids, kind))
    return pairs


def rating_pairs(feedback: Iterable[Mapping[str, Any]]) -> list[Pair]:
    """Pairs from answers rated up and down for the same question as read, at most
    `MAX_PAIRS_A_QUESTION` a question."""
    by_question: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for rating in feedback:
        exchange = rating.get("exchange")
        if not exchange or rating.get("rating") not in ("up", "down"):
            continue
        key = normalise_question(str(exchange.get("standalone") or ""))
        by_question.setdefault(key, {"up": [], "down": []})[rating["rating"]].append(exchange)
    pairs = []
    for rated in by_question.values():
        made = 0
        for good, bad in product(rated["up"], rated["down"]):
            if made == MAX_PAIRS_A_QUESTION or good.get("text") == bad.get("text"):
                continue
            prompt, kind = prompt_for(str(good["standalone"]), good.get("kind"), good, bad)
            ids = (str(good.get("request_id")), str(bad.get("request_id")))
            pairs.append(Pair(prompt, good["text"], bad["text"], "ratings", READERS, ids, kind))
            made += 1
    return pairs


def validator_pair(
    question: str,
    kind: str | None,
    final: Mapping[str, Any],
    draft: str | None,
    ids: tuple[str, ...],
) -> Pair | None:
    """The revision that passed the validator's check over the draft it sent back."""
    validation = final.get("validation") or {}
    passed = validation.get("checked") and validation.get("faithful")
    if not draft or not passed or draft == final.get("text"):
        return None
    prompt, prompt_kind = prompt_for(question, kind, final)
    return Pair(prompt, str(final["text"]), draft, "validator", VALIDATOR, ids, prompt_kind)


def exchange_validator_pairs(feedback: Iterable[Mapping[str, Any]]) -> list[Pair]:
    """Validator pairs from the exchanges kept with ratings, whatever their rating."""
    pairs = []
    for rating in feedback:
        exchange = rating.get("exchange") or {}
        if exchange.get("revisions"):
            pair = validator_pair(
                str(exchange.get("standalone") or ""),
                exchange.get("kind"),
                exchange,
                exchange.get("draft"),
                (str(exchange.get("request_id")),),
            )
            if pair is not None:
                pairs.append(pair)
    return pairs


def run_validator_pairs(
    answers: Mapping[str, Mapping[str, Any]],
    drafts: Mapping[str, Mapping[str, Any]],
    questions: Mapping[str, str],
) -> list[Pair]:
    """Validator pairs from a local evaluation run of the copilot: its answers, its drafts
    before validation and its questions, by id."""
    pairs = []
    for question_id, final in answers.items():
        draft = drafts.get(question_id)
        if not final.get("revisions") or draft is None or question_id not in questions:
            continue
        pair = validator_pair(
            questions[question_id], final.get("kind"), final, draft.get("text"), (question_id,)
        )
        if pair is not None:
            pairs.append(pair)
    return pairs
