"""What the API reads and returns, as Pydantic models: the OpenAPI schema comes from these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_QUESTION = 2000  # characters; a longer question is refused before any model call
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class AskRequest(BaseModel):
    """One question, optionally continuing a conversation."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION,
        description="The question, as the user asked it.",
        examples=["What was 3M's capital expenditure in 2018?"],
    )
    thread_id: str | None = Field(
        default=None,
        pattern=ID_PATTERN,
        description="A conversation's id: give it again to ask a follow-up. A new one if empty.",
    )
    user_id: str | None = Field(
        default=None,
        pattern=ID_PATTERN,
        description=(
            "Whose notes to read and keep (step 5.5). Without one the caller is anonymous, and "
            "nothing is noted about them."
        ),
    )
    retry_of: str | None = Field(
        default=None,
        pattern=ID_PATTERN,
        description=(
            "An earlier answer's request id: answer its question again, as it was read, with "
            "another model setting, in a conversation of its own and never from the cache "
            "(step 9.2). `question` is then ignored."
        ),
    )

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the question is blank")
        return value.strip()


class FeedbackRequest(BaseModel):
    """A reader's verdict on one answer: thumbs up or down, and an optional comment."""

    model_config = ConfigDict(extra="forbid")

    thread_id: str = Field(pattern=ID_PATTERN, description="The conversation the answer is in.")
    turn: int | None = Field(default=None, ge=1, description="Which answer in it, from 1.")
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=MAX_QUESTION)
    request_id: str | None = Field(
        default=None, pattern=ID_PATTERN, description="The answer's X-Request-ID, if known."
    )


class FeedbackReceipt(BaseModel):
    id: int


class PreferenceRequest(BaseModel):
    """A reader's pick between an answer and a second answer to the same question."""

    model_config = ConfigDict(extra="forbid")

    first: str = Field(pattern=ID_PATTERN, description="The first answer's request id.")
    second: str = Field(pattern=ID_PATTERN, description="The second answer's request id.")
    chosen: Literal["first", "second", "neither"]
    comment: str = Field(default="", max_length=MAX_QUESTION)


class SourcePage(BaseModel):
    """One page of a filing, as an answer cites it."""

    doc_name: str
    page: int = Field(description="0-based, as the citations count; the PDF page is one more.")
    label: str
    section: str | None
    text: str


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    commit: str = "unknown"  # the commit the running image was built from


class Readiness(BaseModel):
    ready: bool
    checks: dict[str, bool]
