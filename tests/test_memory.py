"""Memory: follow-up rewriting, and notes kept about a user."""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.store.memory import InMemoryStore

from copilot.agents.memory import (
    MAX_TURNS,
    NOTES_ROLE,
    REWRITE_ROLE,
    Note,
    Operation,
    apply,
    extract,
    note_id,
    recall,
    reconcile,
    rewrite_followup,
)
from copilot.eval.financebench import read_jsonl
from copilot.ingest.universe import read_companies
from copilot.llm import FakeLLM

TURN = ("What was Netflix's revenue in 2022?", "Netflix's revenue was $31.6 billion in 2022 [1].")


def standalone(text: str) -> str:
    return json.dumps({"standalone": text})


def test_a_first_question_without_notes_makes_no_call() -> None:
    llm = FakeLLM([])

    result = rewrite_followup(llm, [], "What was Netflix's revenue in 2022?")

    assert (result.standalone, result.rewritten) == ("What was Netflix's revenue in 2022?", False)
    assert llm.calls == []


def test_a_follow_up_is_rewritten_from_the_conversation() -> None:
    llm = FakeLLM([standalone("What was Netflix's revenue in 2021?")])

    result = rewrite_followup(llm, [TURN], "And in 2021?", ["Follows Netflix."])

    assert result.standalone == "What was Netflix's revenue in 2021?"
    assert result.rewritten
    assert llm.calls[0].role == REWRITE_ROLE == "strong"
    prompt = llm.calls[0].messages[1]["content"]
    assert "Q1: What was Netflix's revenue in 2022?" in prompt
    assert "A1: Netflix's revenue was $31.6 billion" in prompt
    assert "- Follows Netflix." in prompt
    assert "New question: And in 2021?" in prompt


def test_only_the_last_turns_are_sent() -> None:
    turns = [(f"Question {n}?", f"Answer {n}.") for n in range(1, 6)]
    llm = FakeLLM([standalone("Question 6?")])

    rewrite_followup(llm, turns, "And the next?")

    prompt = llm.calls[0].messages[1]["content"]
    assert "Question 1?" not in prompt
    assert prompt.count("\nA") == MAX_TURNS


def test_an_unreadable_rewrite_keeps_the_question() -> None:
    result = rewrite_followup(FakeLLM(["no JSON here"]), [TURN], "And in 2021?")

    assert (result.standalone, result.rewritten) == ("And in 2021?", False)
    assert result.error is not None


def test_an_unchanged_question_is_not_counted_as_rewritten() -> None:
    question = "What was Boeing's revenue in 2022?"

    result = rewrite_followup(FakeLLM([standalone(question)]), [TURN], question)

    assert not result.rewritten


def test_extract_keeps_facts_about_the_user() -> None:
    llm = FakeLLM([json.dumps({"facts": ["Follows Netflix. ", " "]})])

    facts = extract(llm, "I follow Netflix; what was its revenue?", "It was $31.6 billion.")

    assert facts == ["Follows Netflix."]
    assert llm.calls[0].role == NOTES_ROLE == "small"
    assert extract(FakeLLM(["?"]), "q", "a") == []


def test_reconcile_asks_only_when_there_are_facts() -> None:
    llm = FakeLLM([json.dumps({"operations": [{"action": "add", "text": "Follows Boeing."}]})])
    notes = [Note("a1", "Follows Netflix.")]

    assert reconcile(llm, notes, []) == []
    operations = reconcile(llm, notes, ["Follows Boeing."])

    assert operations == [Operation(action="add", text="Follows Boeing.")]
    assert "- id a1: Follows Netflix." in llm.calls[0].messages[1]["content"]


def test_apply_adds_updates_and_deletes_notes() -> None:
    store = InMemoryStore()
    apply(store, "u1", [Operation(action="add", text="Follows Netflix.")])
    apply(store, "u1", [Operation(action="add", text="Likes figures in billions.")])
    netflix, billions = recall(store, "u1")

    done = apply(
        store,
        "u1",
        [
            Operation(action="update", id=netflix.id, text="Follows Netflix and Boeing."),
            Operation(action="delete", id=billions.id),
            Operation(action="delete", id="unknown"),
            Operation(action="none", text="Follows Netflix."),
        ],
    )

    assert done == {"add": 0, "update": 1, "delete": 1}
    assert [note.text for note in recall(store, "u1")] == ["Follows Netflix and Boeing."]
    assert recall(store, "another user") == []


def test_a_note_has_a_stable_id_and_is_not_added_twice() -> None:
    store = InMemoryStore()
    twice = [
        Operation(action="add", text="Follows Netflix."),
        Operation(action="add", text="Follows  Netflix."),
    ]

    done = apply(store, "u1", twice)

    assert done["add"] == 1
    assert [note.id for note in recall(store, "u1")] == [note_id("u1", "Follows Netflix.")]
    assert note_id("u2", "Follows Netflix.") != note_id("u1", "Follows Netflix.")


def test_the_memory_set_is_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    conversations = read_jsonl(root / "eval" / "memory" / "conversations.jsonl")
    notes = {
        record["user"]: record for record in read_jsonl(root / "eval" / "memory" / "notes.jsonl")
    }
    names = {company.name for company in read_companies()}

    assert len({c["id"] for c in conversations}) == len(conversations)
    assert {c["user"] for c in conversations} == set(notes)
    for conversation in conversations:
        for turn in conversation["turns"]:
            assert turn["kind"] in ("standalone", "follow-up", "from notes")
            assert set(turn["companies"]) <= names
            assert turn["question"].strip()
            assert turn["answer"].strip()
