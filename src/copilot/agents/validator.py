"""The validator: check a draft's claims against its sources, revise it, or say what failed.

A grounded answer can still say more than its pages: a figure remembered rather than read,
two facts merged into one sentence, a cause the page doesn't give. In Phase 3, 37% of the
doc agent's answers to FinanceBench dev questions had at least one such sentence (faithful
0.63). The validator checks every cited answer before it reaches the user (step 5.3):

1. **Check.** `copilot.eval.faithfulness.check` asks a model whether each sentence is
   supported by the sources it cites, with the calculator's expressions. It runs on the
   gateway's `small` role: a model other than the answer's writer (the `strong` role) and
   other than the evaluation's judge (Qwen, the `fast` role), so the copilot is never
   tuned to the judge that grades it.
2. **Revise.** When a sentence fails, the writer gets the question, the same sources, its
   answer and the failing sentences, and writes the answer again so that every sentence
   is supported: each failing sentence corrected from the sources, or dropped.
3. **At most twice.** If the answer still fails after two revisions, the sentences that
   passed are kept and the rest are reported as unverified; with none left, the copilot
   declines.

A question that asks for a judgement (whether a margin is healthy, a trend improving) needs
one, and the sources seldom state it in so many words, so the check rejected such
sentences and the revisions dropped them: in the end-to-end run, right answers lost their
verdicts (step 5.6). Since version 2 the writer may keep a judgement the supported facts
bear out as a sentence of its own that begins "Assessment:" (`ASSESSMENT`). The check
still reads it, but it doesn't fail the answer, and trimming keeps it beside at least one
supported sentence, so a reader sees what the sources state and what the answer concludes
from them, apart.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any

from copilot.answer.calculator import Calculation
from copilot.answer.context import Source
from copilot.answer.generate import ROLE as WRITER_ROLE
from copilot.answer.generate import Answer, build_answer, citations
from copilot.eval.faithfulness import Faithfulness, SentenceCheck, check
from copilot.llm import LLMClient, Message, ModelRole, system, user

CHECK_ROLE: ModelRole = "small"
MAX_REVISIONS = 2
PROMPT_VERSION = "2"  # 2: a labelled assessment may stay; percentages computed as such
ASSESSMENT = "Assessment:"

REVISE_INSTRUCTION = """\
A check found that these sentences of your answer are not supported by the sources they \
cite:

{failing}

Write the answer again under the same rules, so that every sentence is supported by the \
sources it cites: correct each of these sentences from the sources, or leave it out. Keep \
the sentences that are supported. If the question asks for a judgement, such as whether a \
margin is healthy or a trend improving, and the supported facts bear one out, give it as \
the last sentence, beginning "Assessment:", with the citations of the facts it rests on \
and no new facts. Compute every figure with "calculations" again, as the rules say; for a \
percentage, the expression multiplies by 100, as in (a - b) / b * 100. Return the same \
JSON object."""


def check_answer(llm: LLMClient, answer: Answer) -> Faithfulness:
    """Each sentence of `answer` checked against the sources it cites, on the small role."""
    sources = {source.number: (source.label, source.text) for source in answer.sources}
    calculations = [(c.id, c.expression, c.value) for c in answer.calculations]
    return check(llm, answer.text, sources, calculations, role=CHECK_ROLE)


def labelled(text: str) -> bool:
    """Whether a sentence is the answer's own assessment, labelled as such."""
    return text.lstrip().startswith(ASSESSMENT)


def failing(verdict: Faithfulness) -> list[SentenceCheck]:
    """The sentences that aren't supported, including those that cite nothing; a labelled
    assessment doesn't fail."""
    return [s for s in verdict.checks if s.supported is not True and not labelled(s.text)]


def passes(verdict: Faithfulness) -> bool:
    """Every sentence is supported by its sources or is a labelled assessment, and at least
    one is supported."""
    return not failing(verdict) and verdict.supported_sentences > 0


def revise_messages(
    system_prompt: str, question: str, answer: Answer, failed: Sequence[SentenceCheck]
) -> list[Message]:
    blocks = "\n\n".join(f"[{s.number}] {s.label}\n{s.text}" for s in answer.sources)
    listed = "\n".join(
        f"{n}. {sentence.text}" + ("" if sentence.cited else " (it cites no source)")
        for n, sentence in enumerate(failed, start=1)
    )
    return [
        system(system_prompt),
        user(
            f"Question: {question}\n\nSources:\n\n{blocks}\n\n"
            f"Your answer:\n{answer.text}\n\n" + REVISE_INSTRUCTION.format(failing=listed)
        ),
    ]


def revise(
    llm: LLMClient,
    system_prompt: str,
    question: str,
    answer: Answer,
    failed: Sequence[SentenceCheck],
) -> Answer:
    """The answer written again by its writer, with the failing sentences pointed out."""
    response = llm.complete(
        revise_messages(system_prompt, question, answer, failed),
        role=WRITER_ROLE,
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    return build_answer(question, answer.sources, response)


def trim(answer: Answer, verdict: Faithfulness) -> tuple[Answer, list[str]]:
    """The answer cut to its supported sentences and labelled assessments, and the sentences
    that were cut.

    With no supported sentence left, the answer becomes a refusal that names what couldn't
    be verified: an assessment alone answers nothing.
    """
    keep = [s.supported is True or labelled(s.text) for s in verdict.checks]
    kept = [s.text for s, kept in zip(verdict.checks, keep, strict=True) if kept]
    dropped = [s.text for s, kept in zip(verdict.checks, keep, strict=True) if not kept]
    if not verdict.supported_sentences:
        missing = "an answer its sources support; unverified: " + "; ".join(dropped)
        refusal = dataclasses.replace(answer, answerable=False, text="", cited=[], missing=missing)
        return refusal, dropped
    text = " ".join(kept)
    numbers = {source.number for source in answer.sources}
    cited = [number for number in citations(text) if number in numbers]
    return dataclasses.replace(answer, text=text, cited=cited), dropped


# ---------------------------------------------------------------------------------------
# Answers as the graph's state holds them
# ---------------------------------------------------------------------------------------


def to_answer(record: dict[str, Any], question: str) -> Answer:
    """An answer rebuilt from its JSON record (`copilot.agents.graph.answer_record`)."""
    sources = [
        Source(
            number=s["number"],
            doc_name=s["doc_name"],
            page=s["page"],
            label=s["label"],
            text=s["text"],
            tokens=s.get("tokens", len(s["text"]) // 4),
        )
        for s in record["sources"]
    ]
    calculations = [
        Calculation(
            id=c["id"],
            expression=c["expression"],
            decimals=c.get("decimals", 2),
            value=c.get("value"),
            error=c.get("error"),
        )
        for c in record.get("calculations", [])
    ]
    return Answer(
        question=question,
        answerable=record["answerable"],
        text=record["text"],
        missing=record.get("missing", ""),
        sources=sources,
        cited=list(record.get("cited", [c["number"] for c in record.get("citations", [])])),
        calculations=calculations,
        error=record.get("error"),
    )


def verdict_record(verdict: Faithfulness) -> dict[str, Any]:
    return {
        "faithful": passes(verdict),
        "assessments": sum(labelled(s.text) for s in verdict.checks),
        "sentences": len(verdict.checks),
        "supported": verdict.supported_sentences,
        "failing": [dataclasses.asdict(sentence) for sentence in failing(verdict)],
        "model": verdict.model,
        "error": verdict.error,
    }
