"""LLM access: one gateway for every model call, plus a fake for tests."""

from copilot.llm.base import (
    LLMClient,
    LLMError,
    LLMResponse,
    Message,
    ModelRole,
    assistant,
    system,
    user,
)
from copilot.llm.fake import FakeLLM
from copilot.llm.gateway import LLMGateway, build_router

__all__ = [
    "FakeLLM",
    "LLMClient",
    "LLMError",
    "LLMGateway",
    "LLMResponse",
    "Message",
    "ModelRole",
    "assistant",
    "build_router",
    "system",
    "user",
]
